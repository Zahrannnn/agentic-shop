"use client";

import { cn } from "@/shared/utils/cn";

import { PlanRenderer } from "./plan-renderer";
import { StatusStepper } from "./status-stepper";
import type { PlanAction, UiPlan } from "../validations/plan-schema";
import { turnProse, type Turn } from "../store";

/**
 * One transcript turn (Curator's Desk): the shopper's side (a right-aligned
 * Desk bubble for text, a quiet "▸ action" line for a tapped plan action),
 * then the agent's side — stepper while stages arrive, prose at the Body
 * measure, the rendered plan, and an inline Pencil-tone notice for a terminal
 * error or a plan the validation gate rejected. `turn_end` adds nothing.
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
  const lastStage = turn.stages.at(-1) ?? null;
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
        {turn.stages.length > 0 || working ? (
          <StatusStepper
            stages={turn.stages}
            currentStage={working ? lastStage : null}
            working={working}
            foundCount={turn.foundCount}
          />
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
