import { configureStore } from "@reduxjs/toolkit";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sessionSlice } from "../store/session-slice";
import {
  STAGE_ORDER,
  transcriptSlice,
  type Turn,
} from "../store/transcript-slice";
import { useAgentTurn, type SendOutcome } from "./use-agent-turn";

/**
 * The hook under test composes the same slice reducers the real store
 * (`src/shared/store/store.ts`) registers. The singleton store lives behind
 * the `@/` path alias, which vitest cannot resolve in this project (no
 * tsconfig-paths plugin), so the test store is composed locally from the
 * untouched slice reducers instead — identical state shape and behavior.
 */
function createTestStore() {
  return configureStore({
    reducer: {
      agentSession: sessionSlice.reducer,
      agentTranscript: transcriptSlice.reducer,
    },
  });
}

/** Renders one wire frame exactly as the backend does (compact one-line JSON). */
function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const encoder = new TextEncoder();

/** A 200 SSE response whose body replays the given chunks. */
function sseResponse(chunks: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function jsonResponse(status: number, body: unknown): Response {
  return Response.json(body, { status });
}

const VALID_PLAN = {
  planVersion: "1",
  sessionId: "demo-12345",
  turnId: 1,
  root: {
    type: "product_grid",
    props: {
      title: "Top picks for long flights",
      productIds: ["aurora-hush-pro", "cloudline-air"],
      ranked: true,
    },
    actions: [
      {
        type: "add_to_cart",
        label: "Add to cart",
        payload: { productId: "aurora-hush-pro" },
      },
    ],
  },
};

const INVALID_PLAN = {
  planVersion: "1",
  sessionId: "demo-12345",
  turnId: 1,
  root: { type: "hypno_grid", props: {}, actions: [] },
};

/** A cart plan superseding turn 1's plan in place (D2 amendment). */
const AMENDED_CART_PLAN = {
  planVersion: "1",
  sessionId: "demo-12345",
  turnId: 2,
  amendsTurnId: 1,
  root: {
    type: "cart_view",
    props: {
      items: [{ productId: "aurora-hush-pro", quantity: 1 }],
      totalUsd: 179,
    },
    actions: [
      {
        type: "remove_from_cart",
        label: "Remove",
        payload: { productId: "aurora-hush-pro" },
      },
    ],
  },
};

const SESSION_EXPIRED_MESSAGE =
  "Session expired. Starting a fresh conversation.";
const TURN_IN_FLIGHT_MESSAGE =
  "Another reply is still in progress. Please wait for it to finish.";

function currentTurn(turns: Turn[]): Turn {
  const turn = turns.at(-1);
  if (!turn) {
    throw new Error("expected a current turn");
  }
  return turn;
}

describe("useAgentTurn", () => {
  const fetchMock = vi.fn<(url: unknown, init?: unknown) => Promise<Response>>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function renderTurnHook() {
    const store = createTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const rendered = renderHook(() => useAgentTurn(), { wrapper });
    return { ...rendered, store };
  }

  it("streams a happy turn into the store: stages, count, prose, plan, unlock", async () => {
    const streamText = [
      frame("status", { stage: "intent_parsed" }),
      frame("status", { stage: "searching" }),
      frame("status", { stage: "found_n", count: 14 }),
      frame("status", { stage: "researching" }),
      frame("status", { stage: "ranking" }),
      frame("status", { stage: "building_ui" }),
      frame("message_delta", { text: "Based on your priorities, " }),
      frame("message_delta", { text: "here are my top picks." }),
      frame("ui_update", VALID_PLAN),
      frame("turn_end", {}),
    ].join("");
    // Split at awkward offsets: the hook must cope with reassembled frames.
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        streamText.slice(0, 41),
        streamText.slice(41, 118),
        streamText.slice(118),
      ]),
    );
    const { result, store } = renderTurnHook();
    const sessionId = result.current.sessionId;

    let outcome: SendOutcome | undefined;
    await act(async () => {
      outcome = await result.current.send({
        message: "  recommend headphones  ",
      });
    });

    expect(outcome).toEqual({ kind: "started" });
    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    expect(result.current.isBusy).toBe(false);
    expect(result.current.turns).toHaveLength(1);

    const turn = currentTurn(result.current.turns);
    expect(turn.userText).toBe("recommend headphones");
    expect(turn.sentAction).toBeNull();
    expect(turn.stages).toEqual([...STAGE_ORDER]);
    expect(turn.foundCount).toBe(14);
    expect(turn.deltas).toBe(
      "Based on your priorities, here are my top picks.",
    );
    expect(turn.planState).toBe("rendered");
    expect(turn.plan).toEqual(VALID_PLAN);
    expect(turn.terminal).toEqual({ kind: "turn_end" });
    expect(store.getState().agentTranscript.phase).toBe("idle");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("http://127.0.0.1:8000/api/chat");
    expect(JSON.parse(init.body as string)).toEqual({
      session_id: sessionId,
      message: "recommend headphones",
      ui_action: null,
      resume: false,
    });
  });

  it("keeps the sent action verbatim in the turn when uiAction is given", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([frame("turn_end", {})]));
    const { result } = renderTurnHook();

    const uiAction = {
      type: "select_preference",
      label: "Headphones",
      payload: { value: "headphones" },
    };
    await act(async () => {
      await result.current.send({ uiAction });
    });

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const payload = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(payload.ui_action).toEqual(uiAction);
    expect("message" in payload).toBe(false);

    const turn = currentTurn(result.current.turns);
    expect(turn.sentAction).toEqual(uiAction);
    expect(turn.userText).toBeNull();
    expect(turn.terminal).toEqual({ kind: "turn_end" });
  });

  it("recovers from a 404: fresh session id, one visible failed turn, no retry", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(404, { detail: "unknown_session" }),
    );
    const { result, store } = renderTurnHook();
    const sessionIdBefore = result.current.sessionId;

    let outcome: SendOutcome | undefined;
    await act(async () => {
      outcome = await result.current.send({
        message: "still there?",
        resume: true,
      });
    });

    expect(outcome).toEqual({
      kind: "http_error",
      status: 404,
      detail: { detail: "unknown_session" },
    });

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toMatchObject({ resume: true });

    // A fresh session id was minted and the store is unlocked.
    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    expect(result.current.sessionId).not.toBe(sessionIdBefore);
    expect(result.current.sessionId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(store.getState().agentSession.live).toBe(true);

    // Exactly one visible turn: the user's, closed by the system notice.
    expect(result.current.turns).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1); // no auto-retry
    const turn = currentTurn(result.current.turns);
    expect(turn.userText).toBe("still there?");
    expect(turn.terminal).toEqual({
      kind: "error",
      message: SESSION_EXPIRED_MESSAGE,
      code: "unknown_session",
    });
  });

  it("handles a 409 with a retry-affordance failed turn and returns the sentinel", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, { detail: "turn_in_flight" }),
    );
    const { result, store } = renderTurnHook();

    let outcome: SendOutcome | undefined;
    await act(async () => {
      outcome = await result.current.send({ message: "hello" });
    });

    expect(outcome).toEqual({
      kind: "http_error",
      status: 409,
      detail: { detail: "turn_in_flight" },
    });
    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    // The rest of the store is untouched apart from the failed turn.
    expect(result.current.turns).toHaveLength(1);
    const turn = currentTurn(result.current.turns);
    expect(turn.terminal).toEqual({
      kind: "error",
      message: TURN_IN_FLIGHT_MESSAGE,
      code: "busy",
    });
    expect(turn.planState).toBe("none");
    expect(turn.stages).toEqual([]);
    expect(store.getState().agentSession.live).toBe(true);
  });

  it("routes an amendsTurnId plan onto the referenced turn and keeps the mutation turn prose-only", async () => {
    const { result } = renderTurnHook();

    // Turn 1: a normal plan — becomes the amendment anchor.
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame("message_delta", { text: "Here are my picks." }),
        frame("ui_update", VALID_PLAN),
        frame("turn_end", {}),
      ]),
    );
    await act(async () => {
      await result.current.send({ message: "recommend headphones" });
    });

    // Turn 2: the add-to-cart mutation streams a plan carrying amendsTurnId.
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame("message_delta", { text: "Added to your cart." }),
        frame("ui_update", AMENDED_CART_PLAN),
        frame("turn_end", {}),
      ]),
    );
    await act(async () => {
      await result.current.send({
        uiAction: {
          type: "add_to_cart",
          label: "Add to cart",
          payload: { productId: "aurora-hush-pro" },
        },
      });
    });

    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    const turns = result.current.turns;
    expect(turns).toHaveLength(2);
    // The ANCHOR turn's plan was replaced in place, still "rendered".
    expect(turns[0].planState).toBe("rendered");
    expect(turns[0].plan).toEqual(AMENDED_CART_PLAN);
    // The mutation turn kept no plan — confirmation prose only.
    expect(turns[1].planState).toBe("none");
    expect(turns[1].plan).toBeNull();
    expect(turns[1].deltas).toBe("Added to your cart.");
    expect(turns[1].terminal).toEqual({ kind: "turn_end" });
  });

  it("marks an invalid plan structured_output-invalid and keeps reading to turn_end", async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        frame("status", { stage: "intent_parsed" }),
        frame("message_delta", { text: "Let me show you…" }),
        frame("ui_update", INVALID_PLAN),
        frame("turn_end", {}),
      ]),
    );
    const { result } = renderTurnHook();

    await act(async () => {
      await result.current.send({ message: "surprise me" });
    });

    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    const turn = currentTurn(result.current.turns);
    expect(turn.planState).toBe("invalid");
    // Invalid plans never enter state — the plan stays empty.
    expect(turn.plan).toBeNull();
    expect(turn.terminal).toEqual({
      kind: "error",
      message: expect.stringContaining("Invalid discriminator value"),
      code: "structured_output",
    });
    // The prose streamed before the bad plan is preserved.
    expect(turn.deltas).toBe("Let me show you…");
    expect(turn.stages).toEqual(["intent_parsed"]);
  });

  it("ignores a send while a turn is in flight", async () => {
    let resolveFirst!: (response: Response) => void;
    fetchMock.mockImplementationOnce(
      () => new Promise<Response>((resolve) => (resolveFirst = resolve)),
    );
    const { result } = renderTurnHook();

    await act(async () => {
      const first = result.current.send({ message: "first" });
      const second = await result.current.send({ message: "second" });

      expect(second).toEqual({ kind: "ignored_busy" });
      resolveFirst(sseResponse([frame("turn_end", {})]));
      await first;
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.turns).toHaveLength(1);
    expect(currentTurn(result.current.turns).userText).toBe("first");
    expect(result.current.phase).toBe("idle");
  });

  it("releases the lock when the stream dies without a terminal frame", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const { result } = renderTurnHook();

    let outcome: SendOutcome | undefined;
    await act(async () => {
      outcome = await result.current.send({ message: "hello" });
    });

    expect(outcome?.kind).toBe("network_error");
    await waitFor(() => {
      expect(result.current.phase).toBe("idle");
    });
    const turn = currentTurn(result.current.turns);
    expect(turn.terminal).toEqual({
      kind: "error",
      message: "Connection lost before the reply finished. Please try again.",
      code: "internal",
    });
  });

  it("startFresh clears the transcript and mints a new session id", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse([frame("turn_end", {})]));
    const { result, store } = renderTurnHook();

    await act(async () => {
      await result.current.send({ message: "hello" });
    });
    const sessionIdBefore = result.current.sessionId;
    expect(result.current.turns).toHaveLength(1);

    act(() => {
      result.current.startFresh();
    });

    expect(result.current.turns).toHaveLength(0);
    expect(result.current.phase).toBe("idle");
    expect(result.current.sessionId).not.toBe(sessionIdBefore);
    expect(store.getState().agentTranscript.turns).toHaveLength(0);
  });
});
