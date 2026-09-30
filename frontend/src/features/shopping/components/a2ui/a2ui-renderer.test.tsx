import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PlanAction } from "../../validations/plan-schema";
import {
  parseA2uiBlueprint,
  type A2uiMessage,
} from "../../validations/a2ui-schema";
import { A2uiRenderer } from "./a2ui-renderer";

/**
 * The D10 side-by-side proof: the SAME plan data that the native registry
 * renders also renders through the real A2UI stack (`@a2ui/react` +
 * `@a2ui/web_core`, v0.9) straight from the backend's golden fixtures, and a
 * tap inside the A2UI surface sends the VERBATIM plan action the native path
 * sends (FR-009 holds for both renderers).
 */

const GOLDENS_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../..",
  "backend/fixtures/a2ui",
);

function goldenMessages(name: string): A2uiMessage[] {
  const raw = JSON.parse(readFileSync(resolve(GOLDENS_DIR, name), "utf-8"));
  const result = parseA2uiBlueprint({ messages: raw });
  if (!result.ok) {
    throw new Error(`golden ${name} failed the gate: ${result.errors.join("; ")}`);
  }
  return result.blueprint.messages;
}

describe("A2uiRenderer", () => {
  it("renders the grid fixture through the A2UI stack", () => {
    render(
      <A2uiRenderer
        messages={goldenMessages("product-grid-flights.json")}
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByTestId("a2ui-surface")).toBeInTheDocument();
    // Bound title from the data model (the ChildList demo's sibling binding).
    expect(screen.getByText("Best matches for long flights")).toBeInTheDocument();
  });

  it("renders every golden fixture without crashing", () => {
    for (const name of [
      "cart-one-item.json",
      "comparison-two.json",
      "multi-picker-priorities.json",
      "preference-picker-category.json",
      "product-details.json",
    ]) {
      const { unmount } = render(
        <A2uiRenderer messages={goldenMessages(name)} onAction={vi.fn()} />,
      );
      expect(screen.getByTestId("a2ui-surface")).toBeInTheDocument();
      unmount();
    }
  });

  it("sends the verbatim plan action when a picker chip button is tapped", () => {
    const onAction = vi.fn<(action: PlanAction) => void>();
    render(
      <A2uiRenderer
        messages={goldenMessages("preference-picker-category.json")}
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Headphones" }));
    expect(onAction).toHaveBeenCalledWith({
      type: "select_preference",
      label: "Headphones",
      payload: { value: "headphones" },
    });
  });

  it("shows the error notice instead of crashing for an unprocessable stream", () => {
    // Structural garbage that still passes the loose gate shape.
    render(
      <A2uiRenderer
        messages={
          [
            {
              version: "v0.9",
              updateComponents: {
                surfaceId: "ghost",
                components: [{ id: "root", component: "NotAComponent" }],
              },
            },
          ] as A2uiMessage[]
        }
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByTestId("a2ui-render-error")).toBeInTheDocument();
  });

  it("stamps select_preferences values from the checkbox data model (D11)", () => {
    // The flagship A2UI interactivity demo: the CheckBoxes two-way-bind into
    // the surface's data model; tapping Apply reads the checked options and
    // posts the same stamped action the native renderer sends.
    const onAction = vi.fn<(action: PlanAction) => void>();
    render(
      <A2uiRenderer
        messages={goldenMessages("multi-picker-priorities.json")}
        onAction={onAction}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(5);
    fireEvent.click(checkboxes[0]!); // Noise cancellation
    fireEvent.click(checkboxes[3]!); // Sound quality

    fireEvent.click(screen.getByRole("button", { name: "Show my picks" }));
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0]?.[0].type).toBe("select_preferences");
    expect(onAction.mock.calls[0]?.[0].payload.values).toEqual([
      "Noise cancellation",
      "Sound quality",
    ]);
  });

  it("renders the refinement chips and steppers from the updated goldens", () => {
    render(
      <A2uiRenderer
        messages={goldenMessages("product-grid-flights.json")}
        onAction={vi.fn()}
      />,
    );
    // D11 refine chips render as A2UI Buttons.
    expect(screen.getByRole("button", { name: "ANC only" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Price: low to high" })).toBeInTheDocument();
  });
});
