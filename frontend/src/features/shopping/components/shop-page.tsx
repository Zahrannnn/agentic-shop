"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { SESSION_STORAGE_KEY } from "../store";
import {
  useAgentTurn,
  type AgentTurnInput,
  type SendOutcome,
} from "../hooks/use-agent-turn";
import type { PlanAction } from "../validations/plan-schema";
import { HealthBadge } from "./health-badge";
import { TranscriptTurn } from "./transcript-turn";
import { TurnComposer } from "./turn-composer";

/**
 * The Curator's Desk shop page (feature shell). The page IS the conversation:
 * a slim wordmark header with the backend-mode badge, the transcript, and the
 * composer with its session line. No welcome sections, no nav chrome.
 *
 * Resume policy (FRONTEND_GUIDE.md §6): the hook passes `resume` through
 * verbatim, so the shell owns the flag. It is true only for the very first
 * send after this mount when a sessionStorage snapshot was rehydrated (the
 * reload path); every send afterwards — and any send in a truly fresh
 * session — goes out without it. On a 404 the hook mints the fresh id and
 * fails the turn with the system notice; the shell additionally shows a
 * one-time inline notice above the composer with the "New conversation"
 * affordance.
 */

const subscribeNoop = () => () => {};

function hasRehydratedSession(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (raw === null) {
      return false;
    }
    const parsed: unknown = JSON.parse(raw);
    const sessionId = (parsed as { sessionId?: unknown } | null)?.sessionId;
    return typeof sessionId === "string" && sessionId.length > 0;
  } catch {
    return false;
  }
}

export function ShopPage() {
  const { turns, phase, isBusy, sessionId, send, startFresh } = useAgentTurn();
  const [expiredNotice, setExpiredNotice] = useState(false);
  const resumeRef = useRef(hasRehydratedSession());
  // The session id is random per process/store, so server and client renders
  // would disagree during hydration (React #418). Render it only after mount;
  // useSyncExternalStore flips the flag post-hydration without a setState
  // effect (React Compiler lint).
  const mounted = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
  // Keep the newest turn in view while the agent streams (deltas mutate the
  // turns array, so this fires on every fragment).
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const submit = useCallback(
    async (input: Omit<AgentTurnInput, "resume">): Promise<void> => {
      const outcome: SendOutcome = await send({
        ...input,
        resume: resumeRef.current,
      });
      // Only the first turn of a reattach may carry the resume flag.
      resumeRef.current = false;
      if (outcome.kind !== "ignored_busy") {
        setExpiredNotice(
          outcome.kind === "http_error" && outcome.status === 404,
        );
      }
    },
    [send],
  );

  const handleSendText = useCallback(
    (message: string) => {
      void submit({ message });
    },
    [submit],
  );

  const handleAction = useCallback(
    (action: PlanAction) => {
      void submit({ uiAction: action });
    },
    [submit],
  );

  const handleNewConversation = useCallback(() => {
    resumeRef.current = false;
    setExpiredNotice(false);
    startFresh();
  }, [startFresh]);

  const streaming = phase === "streaming";

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b">
        <div className="flex w-full items-center justify-between px-6 py-4">
          <p className="text-xl font-semibold tracking-tight">agentic-shop</p>
          <HealthBadge />
        </div>
      </header>

      <main className="w-full flex-1 px-6 py-8">
        <div role="log" aria-label="Conversation transcript">
          {turns.length === 0 ? (
            <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
              What are you looking for?
            </p>
          ) : (
            <ol className="space-y-8">
              {turns.map((turn, index) => (
                <li key={turn.id}>
                  <TranscriptTurn
                    turn={turn}
                    isLatest={index === turns.length - 1}
                    isStreaming={streaming && index === turns.length - 1}
                    onAction={handleAction}
                  />
                </li>
              ))}
            </ol>
          )}
          <div ref={transcriptEndRef} aria-hidden="true" />
        </div>
      </main>

      <footer className="border-t">
        <div className="w-full px-6 py-4">
          {expiredNotice ? (
            <div
              data-testid="session-expired-notice"
              className="mb-3 flex items-center justify-between gap-3 rounded-lg border bg-secondary px-4 py-3"
            >
              <p
                role="status"
                className="text-sm leading-[1.6] text-muted-foreground"
              >
                Session expired — starting a fresh conversation.
              </p>
              <button
                type="button"
                onClick={handleNewConversation}
                className="shrink-0 text-xs font-medium uppercase tracking-[0.05em] text-foreground underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                New conversation
              </button>
            </div>
          ) : null}

          <TurnComposer onSend={handleSendText} isBusy={isBusy} />

          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="truncate text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
              Session {mounted ? sessionId.slice(0, 8) : "········"}
            </p>
            <button
              type="button"
              onClick={handleNewConversation}
              className="shrink-0 text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              New conversation
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
