"use client";

import { cn } from "@/shared/utils/cn";

import { STAGE_ORDER, type Stage } from "../store";

/**
 * The turn lifecycle as a horizontal Label-style stage list (DESIGN.md §3
 * Label scale; FRONTEND_GUIDE.md §4 stage order). Stages the stream has not
 * reached yet render in Pencil; completed stages in Ink with their fixed
 * ordinal ("01"…); the stage currently being worked is Teal Ink with a pulsing
 * dot — the only "working" affordance, which the global reduced-motion rule
 * collapses to a static dot (DESIGN.md do #5).
 */

const STAGE_LABELS: Record<Stage, string> = {
  intent_parsed: "Intent",
  searching: "Search",
  found_n: "Found",
  researching: "Research",
  ranking: "Rank",
  building_ui: "UI",
};

export type StatusStepperProps = {
  /** Stages seen so far, in arrival order (the stream guarantees order). */
  stages: Stage[];
  /** The stage the turn is working on right now, if any. */
  currentStage?: Stage | null;
  /** True while the turn is live: adds the subtle working affordance. */
  working?: boolean;
  /** Count carried by the `found_n` status frame, when seen. */
  foundCount?: number;
};

export function StatusStepper({
  stages,
  currentStage = null,
  working = false,
  foundCount,
}: StatusStepperProps) {
  const seen = new Set(stages);
  const currentIndex = currentStage ? STAGE_ORDER.indexOf(currentStage) : -1;
  // A live turn with no status frame yet still shows honest progress: one
  // quiet pulsing dot ahead of the (all-pending) list.
  const showLeadingDot = working && currentIndex < 0;

  return (
    <ol
      aria-label="Agent progress"
      data-testid="status-stepper"
      className="flex flex-wrap items-center gap-x-4 gap-y-1.5"
    >
      {showLeadingDot ? (
        <li data-state="starting">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="size-1.5 animate-pulse rounded-full bg-primary"
            />
            <span className="sr-only">Working</span>
          </span>
        </li>
      ) : null}
      {STAGE_ORDER.map((stage, index) => {
        const isActive = index === currentIndex;
        const isDone = seen.has(stage) && !isActive;
        const isPending = !seen.has(stage) && !isActive;
        return (
          <li
            key={stage}
            data-stage={stage}
            data-state={isActive ? "active" : isDone ? "done" : "pending"}
            aria-current={isActive ? "step" : undefined}
            className={cn(
              "flex items-baseline gap-1.5 text-xs font-medium tracking-[0.05em] uppercase",
              isActive && "text-primary",
              isDone && "text-foreground",
              isPending && "text-muted-foreground",
            )}
          >
            {isActive ? (
              <span
                aria-hidden="true"
                className="size-1.5 self-center animate-pulse rounded-full bg-primary"
              />
            ) : isDone ? (
              <span
                aria-hidden="true"
                className="font-mono text-[10px] text-muted-foreground"
              >
                {String(index + 1).padStart(2, "0")}
              </span>
            ) : null}
            <span>
              {STAGE_LABELS[stage]}
              {stage === "found_n" && typeof foundCount === "number"
                ? ` · ${foundCount}`
                : ""}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
