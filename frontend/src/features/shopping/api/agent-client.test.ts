import { afterEach, describe, expect, it, vi } from "vitest";
import {
  startAgentTurn,
  type ChatRequestBody,
  type TurnHandlers,
} from "./agent-client";

const BASE_URL = "http://127.0.0.1:8000";

const BODY: ChatRequestBody = {
  session_id: "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
  message: "Help me find headphones under $200.",
  resume: false,
};

const UI_PLAN = {
  planVersion: "1",
  sessionId: "demo-12345",
  turnId: 3,
  root: {
    type: "product_grid",
    props: {
      title: "Best matches for long flights",
      productIds: ["aurora-hush-pro", "cloudline-air"],
      ranked: true,
    },
    actions: [
      { type: "compare", label: "Compare", payload: {} },
      {
        type: "add_to_cart",
        label: "Add to cart",
        payload: { productId: "aurora-hush-pro" },
      },
    ],
  },
};

/** Renders one wire frame exactly as the backend does (compact one-line JSON). */
function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const encoder = new TextEncoder();
const encode = (text: string): Uint8Array => encoder.encode(text);

/** The six contracted statuses, two deltas, the plan, the terminator. */
const HAPPY_FRAMES = [
  frame("status", { stage: "intent_parsed" }),
  frame("status", { stage: "searching" }),
  frame("status", { stage: "found_n", count: 14 }),
  frame("status", { stage: "researching" }),
  frame("status", { stage: "ranking" }),
  frame("status", { stage: "building_ui" }),
  frame("message_delta", { text: "Based on your priorities, " }),
  frame("message_delta", { text: "here are my top picks." }),
  frame("ui_update", UI_PLAN),
  frame("turn_end", {}),
];

type RecordedEvent =
  | { kind: "status"; stage: string; count?: number }
  | { kind: "delta"; text: string }
  | { kind: "plan"; plan: unknown }
  | { kind: "turn_end" }
  | { kind: "error"; message: string; code: string }
  | { kind: "http_error"; status: number; detail: unknown };

function createHandlers(): { events: RecordedEvent[]; handlers: TurnHandlers } {
  const events: RecordedEvent[] = [];
  const handlers: TurnHandlers = {
    onStatus: (stage, count) => events.push({ kind: "status", stage, count }),
    onDelta: (text) => events.push({ kind: "delta", text }),
    onPlan: (plan) => events.push({ kind: "plan", plan }),
    onTurnEnd: () => events.push({ kind: "turn_end" }),
    onError: (message, code) => events.push({ kind: "error", message, code }),
    onHttpError: (status, detail) =>
      events.push({ kind: "http_error", status, detail }),
  };
  return { events, handlers };
}

/** A 200 SSE response whose body replays the given chunks, tracking cancel. */
function sseResponse(chunks: string[]): { response: Response; wasCancelled: () => boolean } {
  let cancelled = false;
  let closed = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encode(chunk));
      }
    },
    pull(controller) {
      // The queue drained while a read is still pending: end of stream.
      if (!closed) {
        closed = true;
        controller.close();
      }
    },
    cancel() {
      cancelled = true;
    },
  });
  const response = new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
  return { response, wasCancelled: () => cancelled };
}

/** A non-stream JSON response with the given status. */
function jsonResponse(status: number, body: unknown): Response {
  return Response.json(body, { status });
}

describe("startAgentTurn — request", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the composed JSON body to {base}/api/chat", async () => {
    const fetchMock = vi.fn(async () => sseResponse([frame("turn_end", {})]).response);
    vi.stubGlobal("fetch", fetchMock);
    const { handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(`${BASE_URL}/api/chat`);
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      session_id: BODY.session_id,
      message: BODY.message,
      ui_action: null,
      resume: false,
    });
  });

  it("omits an empty message when a ui_action is present and defaults resume", async () => {
    const fetchMock = vi.fn(async () => sseResponse([frame("turn_end", {})]).response);
    vi.stubGlobal("fetch", fetchMock);
    const { handlers } = createHandlers();

    await startAgentTurn(
      BASE_URL,
      {
        session_id: "demo-12345",
        ui_action: { type: "compare", label: "Compare", payload: {} },
      },
      handlers,
    );

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const payload = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(payload).toEqual({
      session_id: "demo-12345",
      ui_action: { type: "compare", label: "Compare", payload: {} },
      resume: false,
    });
    expect("message" in payload).toBe(false);
  });
});

describe("startAgentTurn — happy stream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a full stream onto handler calls in order, whatever the chunking", async () => {
    const streamText = HAPPY_FRAMES.join("");
    const chunks = [
      streamText.slice(0, 37),
      streamText.slice(37, 100),
      streamText.slice(100),
    ];
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(chunks).response));
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "status", stage: "intent_parsed", count: undefined },
      { kind: "status", stage: "searching", count: undefined },
      { kind: "status", stage: "found_n", count: 14 },
      { kind: "status", stage: "researching", count: undefined },
      { kind: "status", stage: "ranking", count: undefined },
      { kind: "status", stage: "building_ui", count: undefined },
      { kind: "delta", text: "Based on your priorities, " },
      { kind: "delta", text: "here are my top picks." },
      { kind: "plan", plan: UI_PLAN },
      { kind: "turn_end" },
    ]);
  });

  it("passes the ui_update data through as the plan envelope (no unwrapping)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sseResponse([frame("ui_update", UI_PLAN), frame("turn_end", {})]).response),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    const planEvents = events.filter((event) => event.kind === "plan");
    expect(planEvents).toHaveLength(1);
    const plan = (planEvents[0] as { kind: "plan"; plan: unknown }).plan;
    // The envelope itself, not a { plan: ... } wrapper.
    expect(plan).toEqual(UI_PLAN);
    expect((plan as { plan?: unknown }).plan).toBeUndefined();
    expect((plan as { root?: unknown }).root).toEqual(UI_PLAN.root);
  });

  it("ignores unknown event names but keeps reading", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse([
          frame("heartbeat", { ts: 123 }),
          frame("message_delta", { text: "hi" }),
          frame("turn_end", {}),
        ]).response,
      ),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "delta", text: "hi" },
      { kind: "turn_end" },
    ]);
  });

  it("flushes a trailing frame the connection cut before its terminator", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse(["event: turn_end\ndata: {}"]).response,
      ),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([{ kind: "turn_end" }]);
  });
});

describe("startAgentTurn — terminal behavior", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stops reading at turn_end and cancels the stream", async () => {
    // Post-terminal frames sit queued in the stream and must never surface.
    const { response, wasCancelled } = sseResponse([
      frame("message_delta", { text: "before" }) + frame("turn_end", {}),
      frame("message_delta", { text: "after" }),
      frame("error", { message: "late failure", code: "internal" }),
    ]);
    vi.stubGlobal("fetch", vi.fn(async () => response));
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "delta", text: "before" },
      { kind: "turn_end" },
    ]);
    expect(wasCancelled()).toBe(true);
  });

  it("routes an in-stream error frame to onError, with no onTurnEnd and no later frames", async () => {
    const { response, wasCancelled } = sseResponse([
      frame("status", { stage: "intent_parsed" }) +
        frame("error", {
          message: "The model returned an invalid response twice.",
          code: "structured_output",
        }),
      frame("turn_end", {}),
    ]);
    vi.stubGlobal("fetch", vi.fn(async () => response));
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "status", stage: "intent_parsed", count: undefined },
      {
        kind: "error",
        message: "The model returned an invalid response twice.",
        code: "structured_output",
      },
    ]);
    expect(wasCancelled()).toBe(true);
  });

  it("reports a malformed data line as an internal error and stops", async () => {
    const { response, wasCancelled } = sseResponse([
      "event: status\ndata: {not-json\n\n",
      frame("turn_end", {}),
    ]);
    vi.stubGlobal("fetch", vi.fn(async () => response));
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      {
        kind: "error",
        message: expect.stringContaining("not valid JSON"),
        code: "internal",
      },
    ]);
    expect(wasCancelled()).toBe(true);
  });
});

describe("startAgentTurn — non-streaming failures", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("routes a 404 JSON body to onHttpError with the parsed detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, { detail: "unknown_session" })),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, { ...BODY, resume: true }, handlers);

    expect(events).toEqual([
      { kind: "http_error", status: 404, detail: { detail: "unknown_session" } },
    ]);
  });

  it("routes a 409 JSON body to onHttpError with the parsed detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(409, { detail: "turn_in_flight" })),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "http_error", status: 409, detail: { detail: "turn_in_flight" } },
    ]);
  });

  it("falls back to the raw text when an error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("gateway timeout", {
            status: 504,
            headers: { "Content-Type": "text/plain" },
          }),
      ),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([{ kind: "http_error", status: 504, detail: "gateway timeout" }]);
  });

  it("routes a non-SSE 200 to onHttpError with status -1 and the body text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, { unexpected: "json" })),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "http_error", status: -1, detail: JSON.stringify({ unexpected: "json" }) },
    ]);
  });

  it("reports a 200 SSE response with no readable body as onHttpError(-1)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(null, {
            status: 200,
            headers: { "Content-Type": "text/event-stream" },
          }),
      ),
    );
    const { events, handlers } = createHandlers();

    await startAgentTurn(BASE_URL, BODY, handlers);

    expect(events).toEqual([
      { kind: "http_error", status: -1, detail: "Response has no readable stream body." },
    ]);
  });
});

describe("startAgentTurn — abort", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("propagates an abort mid-stream as an AbortError", async () => {
    const controller = new AbortController();
    const stream = new ReadableStream<Uint8Array>({
      start(controls) {
        controls.enqueue(encode(frame("status", { stage: "intent_parsed" })));
        controller.signal.addEventListener("abort", () =>
          controls.error(controller.signal.reason),
        );
      },
      // No pull/close: the read stays pending until the abort errors it.
    });
    const response = new Response(stream, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response),
    );

    const events: RecordedEvent[] = [];
    let signalFirstStatus!: () => void;
    const firstStatusSeen = new Promise<void>((resolve) => {
      signalFirstStatus = resolve;
    });
    const handlers: TurnHandlers = {
      onStatus: (stage, count) => {
        events.push({ kind: "status", stage, count });
        signalFirstStatus();
      },
      onDelta: (text) => events.push({ kind: "delta", text }),
      onPlan: (plan) => events.push({ kind: "plan", plan }),
      onTurnEnd: () => events.push({ kind: "turn_end" }),
      onError: (message, code) => events.push({ kind: "error", message, code }),
      onHttpError: (status, detail) =>
        events.push({ kind: "http_error", status, detail }),
    };

    const promise = startAgentTurn(BASE_URL, BODY, handlers, controller.signal);
    await firstStatusSeen;
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(events).toEqual([
      { kind: "status", stage: "intent_parsed", count: undefined },
    ]);
  });
});
