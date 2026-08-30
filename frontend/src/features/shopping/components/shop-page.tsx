"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import type { CatalogProduct } from "../api/catalog-client";
import { SESSION_STORAGE_KEY } from "../store";
import {
  useAgentTurn,
  type AgentTurnInput,
  type SendOutcome,
} from "../hooks/use-agent-turn";
import type { PlanAction } from "../validations/plan-schema";
import { CatalogSheet } from "./catalog-sheet";
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

/** One-tap starters (PRODUCT voice: concrete needs, not marketing). */
const SUGGESTIONS: { label: string; prompt: string }[] = [
  {
    label: "Flights headphones",
    prompt:
      "Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most.",
  },
  {
    label: "Budget noise cancelling",
    prompt: "Best noise cancelling headphones under $100.",
  },
  {
    label: "Lightweight over-ears",
    prompt:
      "Comfortable lightweight over-ear headphones under $250 for long listening sessions.",
  },
];

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
  const [catalogOpen, setCatalogOpen] = useState(false);
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

  // Catalog sheet → chat: closes the sheet and reuses the same submit path
  // as typed sends, so the resume policy and 404 recovery are identical.
  const handleAskAbout = useCallback(
    (product: CatalogProduct) => {
      setCatalogOpen(false);
      void submit({
        message: `Tell me more about the ${product.name} (${product.id}).`,
      });
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
      <header className="sticky top-0 z-10 border-b bg-background">
        <div className="flex w-full items-center justify-between px-6 py-4">
          <p className="text-xl font-semibold tracking-tight">agentic-shop</p>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              data-testid="browse-catalog"
              onClick={() => setCatalogOpen(true)}
            >
              Browse catalog
            </Button>
            <HealthBadge />
          </div>
        </div>
      </header>

      <main className="w-full flex-1 px-6 py-8">
        <div role="log" aria-label="Conversation transcript">
          {turns.length === 0 ? (
            <div data-testid="empty-state" className="max-w-prose space-y-5 py-10">
              <h1 className="text-2xl font-semibold tracking-tight">
                What are you looking for?
              </h1>
              <p className="text-[15px] leading-[1.6] text-muted-foreground">
                Describe what you need — budget, use case, what matters most.
                The agent searches the catalog, compares the field, and commits
                to a pick with its reasons.
              </p>
              <div className="flex flex-wrap gap-2" data-testid="suggestion-chips">
                {SUGGESTIONS.map((suggestion) => (
                  <Button
                    key={suggestion.label}
                    variant="outline"
                    size="sm"
                    data-testid="suggestion-chip"
                    onClick={() => handleSendText(suggestion.prompt)}
                  >
                    {suggestion.label}
                  </Button>
                ))}
              </div>
            </div>
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

      <footer className="sticky bottom-0 z-10 border-t bg-background">
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

      <CatalogSheet
        open={catalogOpen}
        onOpenChange={setCatalogOpen}
        onAskAbout={handleAskAbout}
      />
    </div>
  );
}
