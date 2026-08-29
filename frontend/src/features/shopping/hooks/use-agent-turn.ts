"use client";

import { useCallback, useRef } from "react";

import { agentApiBaseUrl } from "../../../shared/config/env";
import {
  useAppDispatch,
  useAppSelector,
} from "../../../shared/store/hooks";
import {
  startAgentTurn,
  type ChatRequestBody,
  type ChatRequestUiAction,
} from "../api/agent-client";
import {
  STAGE_ORDER,
  deltaAppended,
  phaseSetIdle,
  planInvalid,
  planReceived,
  resetSessionExpired,
  selectIsBusy,
  selectPhase,
  selectSessionId,
  selectTurns,
  stageProgress,
  stageSeen,
  startNewSession,
  transcriptCleared,
  turnEnded,
  turnFailed,
  turnStarted,
  type Stage,
} from "../store";
import { CATALOG_IDS } from "../utils/catalog-refs";
import { parseUiPlan } from "../validations/plan-schema";

/**
 * React binding for one agent turn (FRONTEND_GUIDE.md §4 state machine):
 * composes the request, drives `api/agent-client.ts`, and maps its handler
 * events onto the transcript/session slices.
 *
 * Lifecycle policy (FRONTEND_GUIDE.md §6):
 * - `resume` is passed through verbatim (default false) — the caller decides
 *   when to resume (e.g. the reload path); a brand-new session must not.
 * - 404 → the backend no longer knows the session: the current turn is
 *   failed with a visible system notice, `resetSessionExpired` mints a fresh
 *   session id, and there is NO auto-retry — the component layer re-sends
 *   without `resume` on the next user action.
 * - 409 → a turn raced in-flight (the hook already prevents same-client
 *   re-entry): the current turn is failed with a retry-affordance notice and
 *   the input unlocks. The store keeps the user's turn visible; nothing else
 *   is touched.
 * - Any other non-ok status → the current turn is failed with a generic
 *   message; the details stay available on the returned {@link SendOutcome}.
 *
 * Handlers close over `dispatch` only (stable), so there are no stale-closure
 * issues; the in-flight guard lives in a ref so double invocations in the
 * same tick (StrictMode-style double events) are still a no-op.
 */

const SESSION_EXPIRED_MESSAGE = "Session expired — starting a fresh conversation.";
const TURN_IN_FLIGHT_MESSAGE =
  "Another reply is still in progress. Please wait for it to finish.";
const CONNECTION_LOST_MESSAGE = "Connection lost before the reply finished. Please try again.";

/** What a `send` call actually did — lets the UI branch on HTTP failures. */
export type SendOutcome =
  | { kind: "started" }
  | { kind: "ignored_busy" }
  | { kind: "http_error"; status: number; detail: unknown }
  | { kind: "network_error"; cause: unknown };

/** Input for `send`: a trimmed message, a plan action, or both. */
export type AgentTurnInput = {
  message?: string;
  uiAction?: ChatRequestUiAction;
  resume?: boolean;
};

const STAGE_SET: ReadonlySet<string> = new Set(STAGE_ORDER);

function isLifecycleStage(stage: string): stage is Stage {
  return STAGE_SET.has(stage);
}

export function useAgentTurn() {
  const dispatch = useAppDispatch();
  const turns = useAppSelector(selectTurns);
  const phase = useAppSelector(selectPhase);
  const isBusy = useAppSelector(selectIsBusy);
  const sessionId = useAppSelector(selectSessionId);
  const inFlightRef = useRef(false);

  const send = useCallback(
    async (input: AgentTurnInput): Promise<SendOutcome> => {
      if (inFlightRef.current || isBusy) {
        return { kind: "ignored_busy" };
      }

      const message = (input.message ?? "").trim();
      const uiAction = input.uiAction;
      inFlightRef.current = true;
      dispatch(
        turnStarted({
          userText: message.length > 0 ? message : undefined,
          sentAction: uiAction,
        }),
      );

      const requestBody: ChatRequestBody = {
        session_id: sessionId,
        resume: input.resume ?? false,
        ui_action: uiAction ?? null,
      };
      if (message.length > 0) {
        requestBody.message = message;
      }

      let terminated = false;
      const markTerminated = () => {
        terminated = true;
      };
      // An array (not a `let`) because the assignment happens inside a
      // handler closure the type checker cannot see into.
      const httpFailures: { status: number; detail: unknown }[] = [];

      try {
        await startAgentTurn(agentApiBaseUrl, requestBody, {
          onStatus: (stage, count) => {
            if (!isLifecycleStage(stage)) {
              return;
            }
            if (typeof count === "number") {
              dispatch(stageProgress({ stage, count }));
            } else {
              dispatch(stageSeen(stage));
            }
          },
          onDelta: (text) => {
            dispatch(deltaAppended(text));
          },
          onPlan: (raw) => {
            // Validation gate before the store: invalid plans never render.
            const result = parseUiPlan(raw, CATALOG_IDS);
            if (result.ok) {
              dispatch(planReceived(result.plan));
            } else {
              dispatch(planInvalid(result.errors));
            }
          },
          onTurnEnd: () => {
            markTerminated();
            dispatch(turnEnded());
          },
          onError: (errorMessage, code) => {
            markTerminated();
            dispatch(turnFailed({ message: errorMessage, code }));
          },
          onHttpError: (status, detail) => {
            markTerminated();
            httpFailures.push({ status, detail });
            if (status === 404) {
              // Session expired: one visible failed turn carrying the
              // notice, fresh session id, and no auto-retry (the component
              // layer re-sends without resume on the next user action).
              dispatch(
                turnFailed({
                  message: SESSION_EXPIRED_MESSAGE,
                  code: "unknown_session",
                }),
              );
              dispatch(resetSessionExpired());
              return;
            }
            if (status === 409) {
              dispatch(
                turnFailed({
                  message: TURN_IN_FLIGHT_MESSAGE,
                  code: "busy",
                }),
              );
              return;
            }
            dispatch(
              turnFailed({
                message: `Request failed (HTTP ${status}).`,
                code: "internal",
              }),
            );
          },
        });

        if (!terminated) {
          // Stream closed with no terminal frame (network drop): release the
          // input lock without inventing a terminal outcome.
          dispatch(phaseSetIdle());
        }

        const failure = httpFailures.at(0);
        if (failure) {
          return { kind: "http_error", status: failure.status, detail: failure.detail };
        }
        return { kind: "started" };
      } catch (error) {
        const name = error instanceof Error ? error.name : "";
        if (name === "AbortError") {
          // Nothing should abort an MVP turn; if one ever does, release the
          // lock and let the caller see the abort.
          dispatch(phaseSetIdle());
          throw error;
        }
        dispatch(
          turnFailed({ message: CONNECTION_LOST_MESSAGE, code: "internal" }),
        );
        return { kind: "network_error", cause: error };
      } finally {
        inFlightRef.current = false;
      }
    },
    [dispatch, isBusy, sessionId],
  );

  /** Fresh-session recovery affordance: wipe the transcript, mint a new id. */
  const startFresh = useCallback(() => {
    dispatch(transcriptCleared());
    dispatch(startNewSession());
  }, [dispatch]);

  return { turns, phase, isBusy, sessionId, send, startFresh };
}
