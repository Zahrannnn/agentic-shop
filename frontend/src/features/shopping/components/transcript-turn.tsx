"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/shared/utils/cn";

import { A2uiRenderer } from "./a2ui/a2ui-renderer";
import { PlanRenderer } from "./plan-renderer";
import { reassuranceFor } from "./thinking-copy";
import type { A2uiMessage } from "../validations/a2ui-schema";
import type { PlanAction, UiPlan } from "../validations/plan-schema";
import { STAGE_ORDER, turnProse, type Stage, type Turn } from "../store";

/**
 * One transcript turn (Curator's Desk): the shopper's side (a right-aligned
 * Desk bubble for text, a quiet "▸ action" line for a tapped plan action),
 * then the agent's side — a thinking state while the agent works before prose
 * arrives (an elapsed-seconds counter, plus a LIVE STAGE TRAIL driven by the
 * `status` events once the first one lands: completed steps get a check, the
 * current step is highlighted, and the searching step carries the live
 * `found_n` count; before the first stage, a rotating reassurance line fills
 * the gap), the streamed prose at the Body measure, a plan skeleton while the
 * plan document is being built, the rendered plan itself, and an inline
 * Pencil-tone notice for a terminal error or a plan the validation gate
 * rejected. `turn_end` adds nothing. Stage names render as curator-voice
 * labels, never pipeline vocabulary; `found_n` folds into the searching step
 * as a count rather than a step of its own.
 *
 * Only the latest turn's prose is a live region: the conversation log itself
 * is `role="log"` (implicitly polite), so history never re-announces.
 */

/** Curator-voice labels for the lifecycle stages (FR-003 order). */
const STAGE_LABELS: Record<Stage, string> = {
  intent_parsed: "Understanding your ask",
  searching: "Searching the catalog",
  found_n: "Searching the catalog",
  researching: "Reading reviews",
  ranking: "Comparing the field",
  building_ui: "Composing your results",
};

/**
 * The live stage trail: one row per stage the backend has actually reported,
 * in contracted order. The LAST seen stage is the current one (`aria-current`
 * + emphasis); earlier rows are done (muted + check). `found_n` never renders
 * as a row — it is the searching row's live count.
 */
function StageTrail({ turn }: { turn: Turn }) {
  const seen = turn.stages;
  if (seen.length === 0) {
    return null;
  }
  const current = seen[seen.length - 1];
  const currentKey: Stage = current === "found_n" ? "searching" : current;
  const steps = STAGE_ORDER.filter(
    (stage) => stage !== "found_n" && seen.includes(stage),
  );
  return (
    <ol data-testid="turn-stages" className="space-y-1.5">
      {steps.map((stage) => {
        const isCurrent = stage === currentKey;
        const count =
          stage === "searching" && turn.foundCount !== undefined
            ? ` · ${turn.foundCount} found`
            : "";
        return (
          <li
            key={stage}
            data-testid={`turn-stage-${stage}`}
            aria-current={isCurrent ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 text-sm leading-[1.6]",
              isCurrent ? "font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            <span
              aria-hidden="true"
              className={cn("w-3 shrink-0 text-center", isCurrent && "text-primary")}
            >
              {isCurrent ? "•" : "✓"}
            </span>
            <span>
              {STAGE_LABELS[stage]}
              {count}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * The pre-prose thinking state (`role="status"`): `Thinking… Ns` counts the
 * real wait; once `status` events start arriving the reassurance line is
 * replaced by the live stage trail (the wait is now measurable progress), and
 * the skeleton lines stand in for the prose to come. Text changes only — no
 * new animation — so the global reduced-motion collapse leaves this fully
 * readable. The timer starts at 0 on mount and is cleared on unmount
 * (StrictMode-safe: effect cleanup is the only owner of the interval).
 */
function ThinkingBlock({ turn }: { turn: Turn }) {
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
      {turn.stages.length > 0 ? (
        <StageTrail turn={turn} />
      ) : (
        <p
          data-testid="turn-reassurance"
          className="text-xs leading-[1.6] text-muted-foreground"
        >
          {reassuranceFor(elapsedSeconds)}
        </p>
      )}
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
  /**
   * D12 widget path: when present, quantity steppers patch directly
   * (optimistic, no transcript turn) instead of posting the action.
   */
  onQuantityPatch?: (productId: string, quantity: number) => void;
  /**
   * Which stack renders the plan region (D10 side-by-side): the native
   * registry (default) or the A2UI projection when the turn has one. A turn
   * without a blueprint falls back to native with a small notice.
   */
  rendererKind?: "native" | "a2ui";
};

export function TranscriptTurn({
  turn,
  isLatest,
  isStreaming,
  onAction,
  onQuantityPatch,
  rendererKind = "native",
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

  // D12 widget interception: quantity steppers patch directly (optimistic,
  // no transcript turn) when the shell provides the path; everything else —
  // and every fallback without the path — posts verbatim.
  const handleActionWithPatch = (action: PlanAction): void => {
    if (onQuantityPatch && action.type === "set_quantity") {
      const productId = action.payload.productId;
      const quantity = action.payload.quantity;
      if (typeof productId === "string" && typeof quantity === "number") {
        onQuantityPatch(productId, quantity);
        return;
      }
    }
    onAction(action);
  };

  return (
    <article data-testid="transcript-turn" className="animate-turn-in space-y-4">
      {turn.userText !== null ? (
        <div className="max-w-prose">
          <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
            You asked
          </p>
          <p className="mt-1 text-[15px] leading-[1.6]">{turn.userText}</p>
        </div>
      ) : null}

      {turn.sentAction !== null && turn.userText === null ? (
        <p className="text-sm text-muted-foreground">▸ {turn.sentAction.label}</p>
      ) : null}

      <div className="space-y-4">
        {waitingForProse ? <ThinkingBlock turn={turn} /> : null}

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
          rendererKind === "a2ui" && turn.blueprint !== null ? (
            <A2uiRenderer
              messages={turn.blueprint as A2uiMessage[]}
              onAction={handleActionWithPatch}
            />
          ) : rendererKind === "a2ui" ? (
            <div className="max-w-prose space-y-2">
              <p
                className="text-xs uppercase tracking-[0.05em] text-muted-foreground"
                data-testid="a2ui-missing-notice"
              >
                No A2UI payload for this turn — native render
              </p>
              <PlanRenderer
                plan={turn.plan as UiPlan}
                onAction={handleActionWithPatch}
              />
            </div>
          ) : (
            <PlanRenderer
              plan={turn.plan as UiPlan}
              onAction={handleActionWithPatch}
            />
          )
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
