import { configureStore } from "@reduxjs/toolkit";
import { beforeEach, describe, expect, it } from "vitest";
import type { RootState } from "@/shared/store/store";
import { transcriptCleared } from "./transcript-slice";
import {
  SESSION_STORAGE_KEY,
  loadInitialSessionState,
  markSessionLive,
  persistSessionMiddleware,
  resetSessionExpired,
  selectSessionId,
  sessionSlice,
  startNewSession,
  type SessionState,
} from "./session-slice";

const sessionReducer = sessionSlice.reducer;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function createTestStore() {
  return configureStore({
    reducer: { agentSession: sessionReducer },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().concat(persistSessionMiddleware),
  });
}

describe("session reducers", () => {
  it("startNewSession mints a uuid and marks the session live", () => {
    const before: SessionState = {
      sessionId: "00000000-0000-4000-8000-000000000000",
      live: false,
    };
    const after = sessionReducer(before, startNewSession());
    expect(after.sessionId).toMatch(UUID_PATTERN);
    expect(after.sessionId).not.toBe(before.sessionId);
    expect(after.live).toBe(true);
  });

  it("markSessionLive re-asserts the existing id as live", () => {
    const before: SessionState = { sessionId: "sess-existing-1", live: false };
    const after = sessionReducer(before, markSessionLive());
    expect(after.sessionId).toBe("sess-existing-1");
    expect(after.live).toBe(true);
  });

  it("resetSessionExpired (404 flow) mints a different id and stays live", () => {
    const before = sessionReducer(
      { sessionId: "sess-aaaaaaaa", live: true },
      startNewSession(),
    );
    const after = sessionReducer(before, resetSessionExpired());
    expect(after.sessionId).toMatch(UUID_PATTERN);
    expect(after.sessionId).not.toBe(before.sessionId);
    expect(after.live).toBe(true);

    const again = sessionReducer(after, resetSessionExpired());
    expect(again.sessionId).not.toBe(after.sessionId);
  });

  it("does not react to transcriptCleared — the session id stays stable", () => {
    const state: SessionState = { sessionId: "sess-stable-1", live: true };
    // Reference equality: the reducer deliberately has no extraReducer for
    // transcript actions (see the tie-in note in session-slice.ts).
    expect(sessionReducer(state, transcriptCleared())).toBe(state);
  });
});

describe("selectors", () => {
  it("selectSessionId reads the registered agentSession key", () => {
    const rootState = {
      preferences: { compactMode: true, sidebarCollapsed: false },
      agentSession: { sessionId: "sess-1", live: true },
      agentTranscript: { turns: [], phase: "idle" },
    } satisfies RootState;
    expect(selectSessionId(rootState)).toBe("sess-1");
  });
});

describe("sessionStorage persistence", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("writes the snapshot on session actions", () => {
    const store = createTestStore();
    store.dispatch(startNewSession());

    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string)).toEqual(store.getState().agentSession);
    expect(store.getState().agentSession.live).toBe(true);
  });

  it("updates the snapshot on markSessionLive", () => {
    const store = createTestStore();
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ sessionId: store.getState().agentSession.sessionId, live: false }),
    );
    store.dispatch(markSessionLive());

    const persisted: unknown = JSON.parse(
      window.sessionStorage.getItem(SESSION_STORAGE_KEY) as string,
    );
    expect(persisted).toEqual({ sessionId: store.getState().agentSession.sessionId, live: true });
  });

  it("does not write on foreign actions", () => {
    const store = createTestStore();
    store.dispatch({ type: "transcript/turnStarted" });
    expect(window.sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("loadInitialSessionState round-trips a persisted snapshot", () => {
    const store = createTestStore();
    store.dispatch(startNewSession());

    const rehydrated = loadInitialSessionState();
    expect(rehydrated).toEqual(store.getState().agentSession);
  });

  it("falls back to a fresh live session when storage is corrupt", () => {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, "{not json");
    const state = loadInitialSessionState();
    expect(state.sessionId).toMatch(UUID_PATTERN);
    expect(state.live).toBe(true);
  });

  it("falls back when the snapshot has the wrong shape", () => {
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ sessionId: 42, live: "yes" }),
    );
    const state = loadInitialSessionState();
    expect(state.sessionId).toMatch(UUID_PATTERN);
    expect(state.live).toBe(true);
  });

  it("falls back when no snapshot exists yet", () => {
    const state = loadInitialSessionState();
    expect(state.sessionId).toMatch(UUID_PATTERN);
    expect(state.live).toBe(true);
  });
});
