"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/shared/utils/cn";
import type { MultiPickerProps, PlanAction } from "../../validations/plan-schema";

/**
 * Multi-select "what matters most" ask (D11, Curator's Desk): checkbox rows
 * with a local selection bound by `maxSelect`, and the single
 * `select_preferences` action stamped with the checked options at tap time —
 * the same client-side stamping exception as the grid's `withProduct`, and
 * the one place in the registry a payload is composed client-side (the wire
 * template ships `values: []`).
 *
 * Reaching the bound disables the unchecked rows rather than silently
 * dropping the last tap; `select_preferences` posts only when at least one
 * option is checked.
 */
export type MultiPickerComponentProps = {
  props: MultiPickerProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

export function MultiPicker({ props, actions, onAction }: MultiPickerComponentProps) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const applyAction = actions.find((action) => action.type === "select_preferences");
  const atBound = selected.size >= props.maxSelect;

  const toggle = (option: string): void => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(option)) {
        next.delete(option);
      } else if (!atBound) {
        next.add(option);
      }
      return next;
    });
  };

  return (
    <section data-testid="plan-multi_picker">
      <h2 className="text-xl font-semibold tracking-tight">{props.question}</h2>
      <ul className="mt-4 space-y-2">
        {props.options.map((option, index) => {
          const checked = selected.has(option);
          const disabled = !checked && atBound;
          return (
            <li
              key={option}
              className={cn(
                "flex items-center gap-3 rounded-lg border bg-card px-4 py-3",
                disabled && "opacity-50",
              )}
            >
              <Checkbox
                id={`multi-option-${index}`}
                data-testid="multi-option"
                data-option={option}
                checked={checked}
                disabled={disabled}
                onCheckedChange={() => toggle(option)}
              />
              <Label
                htmlFor={`multi-option-${index}`}
                className="cursor-pointer text-[15px] leading-[1.6]"
              >
                {option}
              </Label>
            </li>
          );
        })}
      </ul>
      {applyAction ? (
        <div className="mt-4">
          <Button
            size="sm"
            data-testid="action-select_preferences"
            disabled={selected.size === 0}
            onClick={() => {
              if (!applyAction) {
                return;
              }
              // The stamping exception (D11): options were picked HERE, so the
              // payload carries them — the backend validates the filled list.
              onAction({
                ...applyAction,
                payload: { ...applyAction.payload, values: [...selected] },
              });
            }}
          >
            {applyAction.label}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
