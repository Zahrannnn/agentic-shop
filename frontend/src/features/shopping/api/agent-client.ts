import {
  createSseStreamExtractor,
  isTerminalFrame,
  parseSseData,
  type SseFrame,
} from "./sse-frame-parser";

/**
 * Transport for one agent turn (D7 wire format): POST `/api/chat` and stream
 * the SSE response into plain callbacks, per
 * specs/001-backend-agent-scaffold/contracts/http-api.md.
 *
 * React-free and store-free: the hook (`hooks/use-agent-turn.ts`) composes the
 * request body and maps these handlers onto Redux actions. There is no retry
 * logic here; HTTP error policy (404/409/422) and session lifecycle live in
 * the hook. An aborted `signal` propagates as the fetch AbortError.
 */

/** `ui_action` wire shape (structural mirror of the plan contract's action). */
export type ChatRequestUiAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
};

/**
 * Outgoing chat request (snake_case per the contract's request-body
 * exception). `message` may be omitted when `ui_action` is present;
 * `startAgentTurn` serializes the body and drops an empty `message` whenever
 * an action rides along.
 */
export type ChatRequestBody = {
  session_id: string;
  message?: string;
  ui_action?: ChatRequestUiAction | null;
  resume?: boolean;
};

/** Callbacks invoked, in stream order, while one turn is being consumed. */
export type TurnHandlers = {
  /** `status` frame: lifecycle stage, with the `found_n` count when present. */
  onStatus: (stage: string, count?: number) => void;
  /** `message_delta` frame: one prose fragment to append, in order. */
  onDelta: (text: string) => void;
  /** `ui_update` frame: the full plan envelope, passed through verbatim. */
  onPlan: (plan: unknown) => void;
  /** `turn_end` terminator: success; nothing follows. */
  onTurnEnd: () => void;
  /** `error` terminator (or an unparsable data line): display-safe message. */
  onError: (message: string, code: string) => void;
  /**
   * Non-streaming failure: `!response.ok` with the parsed (or raw) body as
   * `detail`, or a 200 whose content type is not `text/event-stream`
   * (reported as status -1 with the body text). The stream is never entered.
   */
  onHttpError: (status: number, detail: unknown) => void;
};

/**
 * Serializes the request body: the four contracted fields, with an empty
 * `message` omitted whenever `ui_action` is present (the hook composes the
 * body; this is the wire-level guard).
 */
function buildRequestPayload(body: ChatRequestBody): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    session_id: body.session_id,
    ui_action: body.ui_action ?? null,
    resume: body.resume ?? false,
  };
  const message = body.message ?? "";
  const hasAction = body.ui_action !== undefined && body.ui_action !== null;
  if (message.length > 0 || !hasAction) {
    payload.message = message;
  }
  return payload;
}

/** Reads a non-ok body as parsed JSON, falling back to the raw text. */
async function readErrorDetail(response: Response): Promise<unknown> {
  let raw: string;
  try {
    raw = await response.text();
  } catch {
    return null;
  }
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return raw;
  }
}

/**
 * Dispatches one frame onto the handlers. Returns true when reading must
 * stop: any terminator frame (`turn_end`/`error`), or an unparsable data
 * line (routed to `onError` as `internal`). Unknown event names are ignored.
 */
function dispatchFrame(frame: SseFrame, handlers: TurnHandlers): boolean {
  let data: unknown;
  try {
    data = parseSseData(frame);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    handlers.onError(message, "internal");
    return true;
  }

  switch (frame.event) {
    case "status": {
      const payload = data as { stage?: unknown; count?: unknown };
      if (typeof payload.stage === "string") {
        const count =
          typeof payload.count === "number" ? payload.count : undefined;
        handlers.onStatus(payload.stage, count);
      }
      break;
    }
    case "message_delta": {
      const payload = data as { text?: unknown };
      if (typeof payload.text === "string") {
        handlers.onDelta(payload.text);
      }
      break;
    }
    case "ui_update":
      // The data IS the plan envelope — no unwrapping here.
      handlers.onPlan(data);
      break;
    case "turn_end":
      handlers.onTurnEnd();
      break;
    case "error": {
      const payload = data as { message?: unknown; code?: unknown };
      handlers.onError(
        typeof payload.message === "string"
          ? payload.message
          : "Unknown agent error.",
        typeof payload.code === "string" ? payload.code : "internal",
      );
      break;
    }
    default:
      // Unknown event names are skipped, never fatal.
      break;
  }

  return isTerminalFrame(frame);
}

/**
 * Runs one agent turn to completion: POST the body, then stream every SSE
 * frame into `handlers`. Resolves after the terminal frame (the reader is
 * cancelled and remaining frames are ignored) or when the stream ends.
 * Rejects on network failure or abort (AbortError) — the caller decides.
 */
export async function startAgentTurn(
  baseUrl: string,
  body: ChatRequestBody,
  handlers: TurnHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(buildRequestPayload(body)),
    signal,
  });

  if (!response.ok) {
    handlers.onHttpError(response.status, await readErrorDetail(response));
    return;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("text/event-stream")) {
    let bodyText: unknown = null;
    try {
      bodyText = await response.text();
    } catch {
      // Unreadable body — report null detail.
    }
    handlers.onHttpError(-1, bodyText);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    handlers.onHttpError(-1, "Response has no readable stream body.");
    return;
  }

  const decoder = new TextDecoder();
  const extractor = createSseStreamExtractor();

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    const frames = extractor.push(decoder.decode(value, { stream: true }));
    const stopped = frames.some((frame) => dispatchFrame(frame, handlers));
    if (stopped) {
      // Terminal frame reached (or fatal data line): stop reading; whatever
      // is still buffered in the stream is deliberately dropped.
      await reader.cancel().catch(() => undefined);
      return;
    }
  }

  // Stream closed without a terminator: flush the decoder (a multibyte
  // character may be split across the final chunk boundary), emit any trailing
  // partial frame if the connection was cut mid-frame, then let the caller
  // close the turn.
  extractor.push(decoder.decode());
  const trailing = extractor.flush();
  trailing.some((frame) => dispatchFrame(frame, handlers));
}
