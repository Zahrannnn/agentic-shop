import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/shared/store/store";

/**
 * The six lifecycle stages in contracted order (FRONTEND_GUIDE.md §4).
 * Stages are appended in arrival order — the stream guarantees they are
 * gapless and ordered, so no reordering is applied client-side.
 */
export const STAGE_ORDER = [
  "intent_parsed",
  "searching",
  "found_n",
  "researching",
  "ranking",
  "building_ui",
] as const;

export type Stage = (typeof STAGE_ORDER)[number];

/** The action object sent verbatim on an action-tap turn (wire shape). */
export type SentAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
};

/** How the current turn's terminal frame closed it. */
export type TerminalOutcome =
  | { kind: "turn_end" }
  | { kind: "error"; message: string; code: string };

export type PlanState = "none" | "rendered" | "invalid";

export type TranscriptPhase = "idle" | "streaming";

/**
 * One conversation turn. `plan` stays the raw plan dict — validation happens
 * in the Zod gate (`validations/`), and only validated plans reach
 * `planReceived` (`planState: "rendered"`).
 */
export type Turn = {
  /** Monotonic per conversation; equal to the backend turnId-to-be. */
  id: number;
  userText: string | null;
  sentAction: SentAction | null;
  stages: Stage[];
  /** Count carried by the `found_n` status frame, when seen. */
  foundCount?: number;
  /** All `message_delta` text accumulated in arrival order. */
  deltas: string;
  plan: unknown;
  planState: PlanState;
  terminal: TerminalOutcome | null;
};

export type TranscriptState = {
  turns: Turn[];
  phase: TranscriptPhase;
};

const initialState: TranscriptState = {
  turns: [],
  phase: "idle",
};

function currentTurn(state: TranscriptState): Turn | undefined {
  return state.turns[state.turns.length - 1];
}

/**
 * Client-side turn state machine (FRONTEND_GUIDE.md §4):
 * `turnStarted` moves the phase to `streaming` and stays there while the turn
 * is live; the phase returns to `idle` only via `turnEnded`, `turnFailed`,
 * `transcriptCleared`, or the explicit `phaseSetIdle` escape hatch (stream
 * closed without a terminal frame).
 *
 * Once a terminal outcome is recorded on the turn, every in-turn event
 * (`stageSeen`, `stageProgress`, `deltaAppended`, `planReceived`) is ignored —
 * nothing follows the terminal frame. The phase closers themselves remain
 * idempotent on the outcome: a later `turnEnded` never overwrites an earlier
 * error terminal (e.g. from `planInvalid`) but still releases the input lock.
 */
export const transcriptSlice = createSlice({
  name: "transcript",
  initialState,
  reducers: {
    /** Append a new turn and lock the input (phase → "streaming"). */
    turnStarted: (
      state,
      action: PayloadAction<{ userText?: string; sentAction?: SentAction }>,
    ) => {
      const turn: Turn = {
        id: state.turns.length + 1,
        userText: action.payload.userText ?? null,
        sentAction: action.payload.sentAction ?? null,
        stages: [],
        deltas: "",
        plan: null,
        planState: "none",
        terminal: null,
      };
      state.turns.push(turn);
      state.phase = "streaming";
    },
    /** Append a lifecycle stage to the current turn; duplicates are dropped. */
    stageSeen: (state, action: PayloadAction<Stage>) => {
      const turn = currentTurn(state);
      if (!turn || turn.terminal !== null || turn.stages.includes(action.payload)) {
        return;
      }
      turn.stages.push(action.payload);
    },
    /**
     * `status` frame with a count (the `found_n` stage): appends the stage
     * like `stageSeen` and records the count on the turn. A repeat of an
     * already-seen stage only refreshes the count.
     */
    stageProgress: (
      state,
      action: PayloadAction<{ stage: Stage; count: number }>,
    ) => {
      const turn = currentTurn(state);
      if (!turn || turn.terminal !== null) {
        return;
      }
      if (!turn.stages.includes(action.payload.stage)) {
        turn.stages.push(action.payload.stage);
      }
      turn.foundCount = action.payload.count;
    },
    /** Append one `message_delta` text to the current turn's prose. */
    deltaAppended: (state, action: PayloadAction<string>) => {
      const turn = currentTurn(state);
      if (!turn || turn.terminal !== null) {
        return;
      }
      turn.deltas += action.payload;
    },
    /**
     * Store a validated plan (full replace — never merged with the previous
     * one) on the current turn.
     */
    planReceived: (state, action: PayloadAction<unknown>) => {
      const turn = currentTurn(state);
      if (!turn || turn.terminal !== null) {
        return;
      }
      turn.plan = action.payload;
      turn.planState = "rendered";
    },
    /**
     * The validation gate rejected a `ui_update`: record the invalid state and
     * a terminal `structured_output` error for the turn. The phase is not
     * changed here — the stream still runs to its real terminator, which
     * closes the turn.
     */
    planInvalid: (state, action: PayloadAction<string[]>) => {
      const turn = currentTurn(state);
      if (!turn || turn.terminal !== null) {
        return;
      }
      turn.planState = "invalid";
      turn.terminal = {
        kind: "error",
        message: action.payload.join("; "),
        code: "structured_output",
      };
    },
    /** `turn_end` terminator: unlock the input (phase → "idle"). */
    turnEnded: (state) => {
      const turn = currentTurn(state);
      if (turn && turn.terminal === null) {
        turn.terminal = { kind: "turn_end" };
      }
      state.phase = "idle";
    },
    /** `error` terminator: record it and unlock the input. */
    turnFailed: (
      state,
      action: PayloadAction<{ message: string; code: string }>,
    ) => {
      const turn = currentTurn(state);
      if (turn && turn.terminal === null) {
        turn.terminal = {
          kind: "error",
          message: action.payload.message,
          code: action.payload.code,
        };
      }
      state.phase = "idle";
    },
    /** Explicit unlock for a stream that closed without a terminal frame. */
    phaseSetIdle: (state) => {
      state.phase = "idle";
    },
    /**
     * Fresh-session flow: empty the transcript and idle the phase. Turn ids
     * restart at 1 (a cleared transcript always accompanies a new session).
     * The session id is untouched — see `session-slice.ts`.
     */
    transcriptCleared: (state) => {
      state.turns = [];
      state.phase = "idle";
    },
  },
});

export const {
  turnStarted,
  stageSeen,
  stageProgress,
  deltaAppended,
  planReceived,
  planInvalid,
  turnEnded,
  turnFailed,
  phaseSetIdle,
  transcriptCleared,
} = transcriptSlice.actions;

export const selectTurns = (state: RootState): Turn[] =>
  state.agentTranscript.turns;

export const selectPhase = (state: RootState): TranscriptPhase =>
  state.agentTranscript.phase;

/** The most recent turn, or null while the transcript is empty. */
export const selectCurrentTurn = (state: RootState): Turn | null =>
  state.agentTranscript.turns.at(-1) ?? null;

/** True while a turn is in flight (input lock). */
export const selectIsBusy = (state: RootState): boolean =>
  state.agentTranscript.phase === "streaming";

/** The accumulated agent prose for a turn. */
export const turnProse = (turn: Turn): string => turn.deltas;
