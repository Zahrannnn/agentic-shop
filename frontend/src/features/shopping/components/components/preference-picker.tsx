"use client";

import { Button } from "@/components/ui/button";
import type {
  PlanAction,
  PreferencePickerProps,
} from "../../validations/plan-schema";

/**
 * Clarify-turn picker (Curator's Desk): the question is the Headline, options
 * are hairline chip-buttons. Presentational only — there is no selected state
 * here; each chip dispatches its matching `select_preference` action verbatim
 * (the schema gate guarantees one exists per option).
 */
export type PreferencePickerComponentProps = {
  props: PreferencePickerProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

export function PreferencePicker({
  props,
  actions,
  onAction,
}: PreferencePickerComponentProps) {
  return (
    <section data-testid="plan-preference_picker">
      <h2 className="text-xl font-semibold tracking-tight">{props.question}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {props.options.map((option) => {
          const action = actions.find(
            (candidate) =>
              candidate.type === "select_preference" && candidate.label === option,
          );
          if (!action) {
            return null;
          }
          return (
            <Button
              key={option}
              variant="outline"
              data-testid="action-select_preference"
              onClick={() => onAction(action)}
            >
              {option}
            </Button>
          );
        })}
      </div>
    </section>
  );
}
