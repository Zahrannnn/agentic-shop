"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/shared/utils/cn";

import { PlanRenderer } from "./plan-renderer";
import type { PlanAction, UiPlan } from "../validations/plan-schema";
import { turnProse, type Turn } from "../store";

/**
 * One transcript turn (Curator's Desk): the shopper's side (a right-aligned
 * Desk bubble for text, a quiet "▸ action" line for a tapped plan action),
 * then the agent's side — a thinking skeleton while the agent works before
 * prose arrives, the streamed prose at the Body measure, a plan skeleton while
 * the plan document is being built, the rendered plan itself, and an inline
 * Pencil-tone notice for a terminal error or a plan the validation gate
 * rejected. `turn_end` adds nothing. The internal lifecycle stages are
 * deliberately not rendered (UX review): the skeletons communicate progress
 * without exposing pipeline vocabulary.
 *
 * Only the latest turn's prose is a live region: the conversation log itself
 * is `role="log"` (implicitly polite), so history never re-announces.
 */

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
    <article data-testid="transcript-turn" className="space-y-4">
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
        {waitingForProse ? (
          <div
            role="status"
            data-testid="turn-thinking"
            className="max-w-prose space-y-3"
          >
            <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
              Thinking…
            </p>
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : null}

        {turn.deltas.length > 0 ? (
          <p
            aria-live={isLatest ? "polite" : undefined}
            className={cn(
              "max-w-prose text-[15px] leading-[1.6] whitespace-pre-wrap",
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
