import {
  createSlice,
  type Middleware,
  type UnknownAction,
} from "@reduxjs/toolkit";
import type { RootState } from "@/shared/store/store";

/**
 * Session identity for the shopping conversation (data-model.md `sessionSlice`).
 *
 * `sessionId` is client-generated per conversation (a uuid, 36 chars — within
 * the 8–64 contract bound) and stays stable for the whole conversation. `live`
 * records whether the backend is known to still hold the session: it starts
 * `true`; the 404 resume-recovery flow mints a brand-new id via
 * `resetSessionExpired`.
 */
export type SessionState = {
  sessionId: string;
  live: boolean;
};

/** sessionStorage key for the persisted session snapshot. */
export const SESSION_STORAGE_KEY = "agentic-shop.session";

/**
 * The key the slice is registered under in `src/shared/store/store.ts`
 * (`agentSession`, per data-model.md). The persistence middleware reads the
 * snapshot back off the root state through this key.
 */
const AGENT_SESSION_STATE_KEY = "agentSession";

export function createSessionId(): string {
  return crypto.randomUUID();
}

function isSessionSnapshot(value: unknown): value is SessionState {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.sessionId === "string" &&
    candidate.sessionId.length > 0 &&
    typeof candidate.live === "boolean"
  );
}

function readSessionState(root: unknown): SessionState | null {
  if (typeof root !== "object" || root === null) {
    return null;
  }
  const candidate = (root as Record<string, unknown>)[AGENT_SESSION_STATE_KEY];
  return isSessionSnapshot(candidate) ? candidate : null;
}

function persistSessionState(state: SessionState): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Persistence is best-effort: quota or privacy-mode failures must never
    // break a turn. The next successful session action retries the write.
  }
}

/**
 * Initial state for the session slice. On the server (or any environment
 * without sessionStorage) this returns a blank id — no randomness, so static
 * prerender stays valid. The StoreProvider hydrates the real id on mount.
 */
export function loadInitialSessionState(): SessionState {
  if (typeof window === "undefined") {
    return { sessionId: "", live: true };
  }
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (raw !== null) {
      const parsed: unknown = JSON.parse(raw);
      if (isSessionSnapshot(parsed)) {
        return { sessionId: parsed.sessionId, live: parsed.live };
      }
    }
  } catch {
    // Corrupt snapshot — fall through to a fresh session below.
  }
  return { sessionId: createSessionId(), live: true };
}

/**
 * Writes `{ sessionId, live }` to sessionStorage after every `session/*`
 * action. Store composition (`store.subscribe`) is deliberately not used — a
 * narrow middleware keeps the write tied to the actions that can change the
 * snapshot and stays trivially testable.
 */
export const persistSessionMiddleware: Middleware =
  (api) => (next) => (action) => {
    const result = next(action);
    if (
      typeof action === "object" &&
      action !== null &&
      typeof (action as UnknownAction).type === "string" &&
      (action as UnknownAction).type.startsWith("session/")
    ) {
      const session = readSessionState(api.getState());
      if (session !== null) {
        persistSessionState(session);
      }
    }
    return result;
  };

export const sessionSlice = createSlice({
  name: "session",
  initialState: loadInitialSessionState(),
  reducers: {
    /**
     * Client-only hydration: fills an empty session id from sessionStorage
     * or mints a fresh one. Safe to call on every mount; no-op when already set.
     */
    hydrateSession: (state) => {
      if (state.sessionId.length > 0) {
        return;
      }
      const loaded = loadInitialSessionState();
      state.sessionId = loaded.sessionId;
      state.live = loaded.live;
    },
    /** Start a brand-new conversation with a freshly minted session id. */
    startNewSession: (state) => {
      state.sessionId = createSessionId();
      state.live = true;
    },
    /**
     * 404 resume-recovery (FRONTEND_GUIDE.md §6.3): the backend no longer
     * knows the current id, so mint a fresh one. The turn pipeline dispatches
     * `transcriptCleared` right after this to reset the visible transcript.
     *
     * Tie-in note: `transcriptCleared` on its own deliberately does NOT
     * regenerate the session id — the id stays stable within a conversation
     * (including the fresh-session flow, where only `resetSessionExpired`
     * re-mints it). `sessionSlice` intentionally has no extraReducer for
     * transcript actions.
     */
    resetSessionExpired: (state) => {
      state.sessionId = createSessionId();
      state.live = true;
    },
  },
});

export const { hydrateSession, startNewSession, resetSessionExpired } =
  sessionSlice.actions;

export const selectSessionId = (state: RootState): string =>
  state.agentSession.sessionId;
