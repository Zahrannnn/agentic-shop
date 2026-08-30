"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/shared/utils/cn";

import { PlanRenderer } from "./plan-renderer";
import { reassuranceFor } from "./thinking-copy";
import type { PlanAction, UiPlan } from "../validations/plan-schema";
import { turnProse, type Turn } from "../store";

/**
 * One transcript turn (Curator's Desk): the shopper's side (a right-aligned
 * Desk bubble for text, a quiet "▸ action" line for a tapped plan action),
 * then the agent's side — a thinking state while the agent works before prose
 * arrives (an elapsed-seconds counter, a rotating reassurance line, and a
 * skeleton), the streamed prose at the Body measure, a plan skeleton while
 * the plan document is being built, the rendered plan itself, and an inline
 * Pencil-tone notice for a terminal error or a plan the validation gate
 * rejected. `turn_end` adds nothing. The internal lifecycle stages are
 * deliberately not rendered (UX review): the counter and reassurance copy
 * communicate honest progress without exposing pipeline vocabulary.
 *
 * Only the latest turn's prose is a live region: the conversation log itself
 * is `role="log"` (implicitly polite), so history never re-announces.
 */

/**
 * The pre-prose thinking state (`role="status"`): `Thinking… Ns` counts the
 * real wait, a reassurance line rotates with the elapsed bucket (curator
 * voice, never pipeline words), and the skeleton lines stand in for the prose
 * to come. Text changes only — no new animation — so the global
 * reduced-motion collapse leaves this fully readable. The timer starts at 0
 * on mount and is cleared on unmount (StrictMode-safe: effect cleanup is the
 * only owner of the interval).
 */
function ThinkingBlock() {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsedSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => {
      window.clearInterval(id);
    };
  }, []);

  return (
    <div
      role="status"
      data-testid="turn-thinking"
      className="max-w-prose space-y-3"
    >
      <p className="text-xs font-medium tabular-nums text-muted-foreground">
        Thinking… {elapsedSeconds}s
      </p>
      <p
        data-testid="turn-reassurance"
        className="text-xs leading-[1.6] text-muted-foreground"
      >
        {reassuranceFor(elapsedSeconds)}
      </p>
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}

export type TranscriptTurnProps = {
  turn: Turn;
  /** True for the most recent turn in the transcript. */
  isLatest: boolean;
  /** True while THIS turn is the live, streaming one (input locked). */
  isStreaming: boolean;
  onAction: (action: PlanAction) => void;
};

export function TranscriptTurn({
  turn,
  isLatest,
  isStreaming,
  onAction,
}: TranscriptTurnProps) {
  const working = isStreaming && turn.terminal === null;
  const waitingForProse = working && turn.deltas.length === 0;
  const planIncoming = working && turn.deltas.length > 0 && turn.planState === "none";
  const errorMessage =
    turn.terminal?.kind === "error"
      ? turn.terminal.message
      : turn.planState === "invalid"
        ? "This plan failed validation."
        : null;

  return (
    <article data-testid="transcript-turn" className="animate-turn-in space-y-4">
      {turn.userText !== null ? (
        <div className="flex justify-end">
          <p className="max-w-prose rounded-lg bg-secondary px-4 py-2.5 text-[15px] leading-[1.6] text-secondary-foreground">
            {turn.userText}
          </p>
        </div>
      ) : null}

      {turn.sentAction !== null && turn.userText === null ? (
        <p className="text-sm text-muted-foreground">▸ {turn.sentAction.label}</p>
      ) : null}

      <div className="space-y-4">
        {waitingForProse ? <ThinkingBlock /> : null}

        {turn.deltas.length > 0 ? (
          <p
            aria-live={isLatest ? "polite" : undefined}
            className={cn(
              "max-w-prose text-[15px] leading-[1.6] whitespace-pre-wrap",
              working && "streaming-caret",
            )}
          >
            {turnProse(turn)}
          </p>
        ) : null}

        {planIncoming ? (
          <div
            aria-hidden="true"
            data-testid="plan-skeleton"
            className="max-w-3xl space-y-3 rounded-lg border bg-card p-4"
          >
            <Skeleton className="h-5 w-56" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
          </div>
        ) : null}

        {turn.planState === "rendered" ? (
          <PlanRenderer plan={turn.plan as UiPlan} onAction={onAction} />
        ) : null}

        {errorMessage !== null ? (
          <p
            role="status"
            data-testid="turn-error"
            className="max-w-prose rounded-lg border bg-secondary p-4 text-sm leading-[1.6] text-muted-foreground"
          >
            {errorMessage}
          </p>
        ) : null}
      </div>
    </article>
  );
}
