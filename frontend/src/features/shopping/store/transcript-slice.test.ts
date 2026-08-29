import { describe, expect, it } from "vitest";
import type { RootState } from "@/shared/store/store";
import {
  STAGE_ORDER,
  deltaAppended,
  phaseSetIdle,
  planInvalid,
  planReceived,
  selectCurrentTurn,
  selectIsBusy,
  selectPhase,
  selectTurns,
  stageProgress,
  stageSeen,
  transcriptCleared,
  transcriptSlice,
  turnEnded,
  turnFailed,
  turnProse,
  turnStarted,
  type TranscriptState,
  type Turn,
} from "./transcript-slice";

const transcriptReducer = transcriptSlice.reducer;

const initialState: TranscriptState = { turns: [], phase: "idle" };

function withTurn(overrides: Partial<Turn> = {}): TranscriptState {
  const turn: Turn = {
    id: 1,
    userText: "recommend headphones",
    sentAction: null,
    stages: [],
    deltas: "",
    plan: null,
    planState: "none",
    terminal: null,
    ...overrides,
  };
  return { turns: [turn], phase: "streaming" };
}

function currentTurn(state: TranscriptState): Turn {
  const turn = state.turns[state.turns.length - 1];
  if (!turn) {
    throw new Error("expected a current turn");
  }
  return turn;
}

const ERROR_TERMINAL = {
  kind: "error" as const,
  message: "boom",
  code: "internal",
};

describe("turn lifecycle (FRONTEND_GUIDE.md §4 state machine)", () => {
  it("walks the happy path: start → six stages → deltas → plan → turn_end → idle", () => {
    let state = transcriptReducer(
      initialState,
      turnStarted({ userText: "recommend headphones" }),
    );

    expect(state.phase).toBe("streaming");
    expect(state.turns).toHaveLength(1);
    expect(currentTurn(state).id).toBe(1);
    expect(currentTurn(state).userText).toBe("recommend headphones");
    expect(currentTurn(state).sentAction).toBeNull();

    for (const stage of STAGE_ORDER) {
      state = transcriptReducer(state, stageSeen(stage));
    }
    expect(currentTurn(state).stages).toEqual([...STAGE_ORDER]);

    for (const text of ["Over-ear ", "with ANC", ", ranked."]) {
      state = transcriptReducer(state, deltaAppended(text));
    }
    expect(currentTurn(state).deltas).toBe("Over-ear with ANC, ranked.");

    const plan = {
      planVersion: "1",
      sessionId: "sess-1",
      turnId: 1,
      root: { type: "text_block", props: { body: "hi" }, actions: [] },
    };
    state = transcriptReducer(state, planReceived(plan));
    expect(currentTurn(state).planState).toBe("rendered");
    expect(currentTurn(state).plan).toEqual(plan);

    state = transcriptReducer(state, turnEnded());
    expect(state.phase).toBe("idle");
    expect(currentTurn(state).terminal).toEqual({ kind: "turn_end" });
  });

  it("assigns monotonically increasing turn ids across turns", () => {
    let state = transcriptReducer(initialState, turnStarted({ userText: "one" }));
    state = transcriptReducer(state, turnEnded());
    state = transcriptReducer(state, turnStarted({ userText: "two" }));
    expect(state.turns.map((turn) => turn.id)).toEqual([1, 2]);
  });

  it("records action turns with a null user text and phase streaming", () => {
    const sentAction = {
      type: "compare",
      label: "Compare side by side",
      payload: { productIds: ["p1", "p2"] },
    };
    const state = transcriptReducer(initialState, turnStarted({ sentAction }));
    expect(state.phase).toBe("streaming");
    expect(currentTurn(state).sentAction).toEqual(sentAction);
    expect(currentTurn(state).userText).toBeNull();
  });
});

describe("stage handling", () => {
  it("dedupes stages and preserves arrival order", () => {
    let state = withTurn();
    state = transcriptReducer(state, stageSeen("searching"));
    state = transcriptReducer(state, stageSeen("searching"));
    state = transcriptReducer(state, stageSeen("intent_parsed"));
    state = transcriptReducer(state, stageSeen("searching"));
    expect(currentTurn(state).stages).toEqual(["searching", "intent_parsed"]);
  });

  it("stageProgress records the found_n count once and dedupes the stage", () => {
    let state = withTurn();
    state = transcriptReducer(state, stageProgress({ stage: "found_n", count: 3 }));
    state = transcriptReducer(state, stageProgress({ stage: "found_n", count: 3 }));
    expect(currentTurn(state).stages).toEqual(["found_n"]);
    expect(currentTurn(state).foundCount).toBe(3);
  });

  it("ignores stage events when the transcript is empty", () => {
    let state = transcriptReducer(initialState, stageSeen("searching"));
    state = transcriptReducer(state, stageProgress({ stage: "found_n", count: 2 }));
    expect(state.turns).toHaveLength(0);
  });
});

describe("terminal handling", () => {
  it("ignores in-turn actions once a terminal outcome is recorded", () => {
    let state = withTurn({ terminal: ERROR_TERMINAL });
    state = transcriptReducer(state, stageSeen("searching"));
    state = transcriptReducer(state, stageProgress({ stage: "found_n", count: 2 }));
    state = transcriptReducer(state, deltaAppended("late text"));
    state = transcriptReducer(state, planReceived({ planVersion: "1" }));

    const turn = currentTurn(state);
    expect(turn.stages).toEqual([]);
    expect(turn.foundCount).toBeUndefined();
    expect(turn.deltas).toBe("");
    expect(turn.planState).toBe("none");
    expect(turn.terminal).toEqual(ERROR_TERMINAL);
  });

  it("a late turnEnded never overwrites an error terminal but still unlocks", () => {
    let state = withTurn({ terminal: ERROR_TERMINAL });
    state = transcriptReducer(state, turnEnded());
    expect(currentTurn(state).terminal).toEqual(ERROR_TERMINAL);
    expect(state.phase).toBe("idle");
  });

  it("turnFailed records the error terminal and unlocks", () => {
    let state = withTurn({ stages: ["intent_parsed", "searching"] });
    state = transcriptReducer(
      state,
      turnFailed({ message: "model failed", code: "internal" }),
    );
    expect(state.phase).toBe("idle");
    expect(currentTurn(state).terminal).toEqual({
      kind: "error",
      message: "model failed",
      code: "internal",
    });
  });

  it("planInvalid stores the invalid plan state and a structured_output terminal", () => {
    let state = withTurn({ stages: ["building_ui"] });
    state = transcriptReducer(
      state,
      planInvalid(["root.type: invalid_literal", "productIds[0]: unknown id"]),
    );
    const turn = currentTurn(state);
    expect(turn.planState).toBe("invalid");
    expect(turn.terminal).toEqual({
      kind: "error",
      message: "root.type: invalid_literal; productIds[0]: unknown id",
      code: "structured_output",
    });
    // The stream still runs to its real terminator; the phase closes there.
    expect(state.phase).toBe("streaming");
    state = transcriptReducer(state, turnEnded());
    expect(state.phase).toBe("idle");
    expect(currentTurn(state).terminal?.kind).toBe("error");
  });

  it("phaseSetIdle releases the lock without touching the turn", () => {
    const state = transcriptReducer(withTurn(), phaseSetIdle());
    expect(state.phase).toBe("idle");
    expect(currentTurn(state).terminal).toBeNull();
  });

  it("ignores closers on an empty transcript beyond idling the phase", () => {
    let state = transcriptReducer(initialState, turnEnded());
    expect(state.turns).toHaveLength(0);
    expect(state.phase).toBe("idle");
    state = transcriptReducer(initialState, turnFailed({ message: "x", code: "y" }));
    expect(state.phase).toBe("idle");
  });
});

describe("transcriptCleared", () => {
  it("empties the transcript and idles the phase", () => {
    const state = transcriptReducer(
      withTurn({ stages: ["searching"], deltas: "partial" }),
      transcriptCleared(),
    );
    expect(state).toEqual({ turns: [], phase: "idle" });
  });

  it("restarts turn ids at 1 for the fresh session", () => {
    let state = withTurn({ id: 3 });
    state = transcriptReducer(state, transcriptCleared());
    state = transcriptReducer(state, turnStarted({ userText: "fresh start" }));
    expect(currentTurn(state).id).toBe(1);
  });
});

describe("selectors and helpers", () => {
  const turn: Turn = {
    id: 2,
    userText: null,
    sentAction: { type: "details", label: "Details", payload: { productId: "p1" } },
    stages: ["intent_parsed"],
    deltas: "prose",
    plan: { planVersion: "1" },
    planState: "rendered",
    terminal: null,
  };

  const rootState = {
    preferences: { compactMode: true, sidebarCollapsed: false },
    agentSession: { sessionId: "sess-1", live: true },
    agentTranscript: { turns: [turn], phase: "streaming" },
  } satisfies RootState;

  it("selectTurns returns the turn list", () => {
    expect(selectTurns(rootState)).toEqual([turn]);
  });

  it("selectPhase returns the phase and selectIsBusy mirrors streaming", () => {
    expect(selectPhase(rootState)).toBe("streaming");
    expect(selectIsBusy(rootState)).toBe(true);
    expect(
      selectIsBusy({ ...rootState, agentTranscript: { turns: [], phase: "idle" } }),
    ).toBe(false);
  });

  it("selectCurrentTurn returns the last turn, or null when empty", () => {
    expect(selectCurrentTurn(rootState)).toEqual(turn);
    expect(
      selectCurrentTurn({ ...rootState, agentTranscript: { turns: [], phase: "idle" } }),
    ).toBeNull();
  });

  it("turnProse returns the accumulated prose", () => {
    expect(turnProse(turn)).toBe("prose");
  });
});
