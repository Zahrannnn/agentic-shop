import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { parseUiPlan, type PlanComponent, type UiPlan } from "../validations/plan-schema";
import { CATALOG_IDS } from "../utils/catalog-refs";
import { PlanRenderer } from "./plan-renderer";

// Fixture resolution assumes the monorepo root: `frontend/` and `backend/` are
// siblings in one checkout. From `src/features/shopping/components/` it is
// exactly five levels up. Paths go through node:path (not the global URL):
// vitest's jsdom environment swaps in jsdom's URL constructor, which resolves
// against http://localhost (same pattern as plan-schema.test.ts).
const COMPONENTS_DIR = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = resolve(
  COMPONENTS_DIR,
  "../../../../..",
  "backend/fixtures/ui-plans",
);

type FixtureName =
  | "product-grid-flights"
  | "preference-picker-category"
  | "comparison-two"
  | "product-details"
  | "cart-one-item";

const loadFixture = (name: FixtureName): unknown =>
  JSON.parse(readFileSync(resolve(FIXTURES_DIR, `${name}.json`), "utf8"));

function parseFixture(name: FixtureName): UiPlan {
  const result = parseUiPlan(loadFixture(name), CATALOG_IDS);
  if (!result.ok) {
    throw new Error(`fixture ${name} failed the gate: ${result.errors.join("; ")}`);
  }
  return result.plan;
}

function expectRoot<T extends PlanComponent["type"]>(
  plan: UiPlan,
  type: T,
): Extract<UiPlan["root"], { type: T }> {
  if (plan.root.type !== type) {
    throw new Error(`expected root "${type}", got "${plan.root.type}"`);
  }
  return plan.root as Extract<UiPlan["root"], { type: T }>;
}

function renderPlan(plan: UiPlan): ReturnType<typeof vi.fn> {
  const onAction = vi.fn();
  render(<PlanRenderer plan={plan} onAction={onAction} />);
  return onAction;
}

describe("PlanRenderer with the product-grid fixture", () => {
  it("renders the title, three ranked product rows, and the grid-level compare", () => {
    const plan = parseFixture("product-grid-flights");
    const root = expectRoot(plan, "product_grid");
    const onAction = renderPlan(plan);

    expect(screen.getByTestId("plan-product_grid")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Best matches for long flights" }),
    ).toBeInTheDocument();

    const cards = screen.getAllByTestId("product-card");
    expect(cards).toHaveLength(3);
    expect(cards[0]).toHaveAttribute("data-product-id", "aurora-hush-pro");
    expect(within(cards[0]).getByText("01")).toBeInTheDocument();
    expect(within(cards[1]).getByText("02")).toBeInTheDocument();
    expect(within(cards[2]).getByText("03")).toBeInTheDocument();

    // One button per unique action type: compare grid-level, details and
    // add_to_cart attached to every card.
    expect(screen.getByRole("button", { name: "Compare" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Details" })).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Add to cart" })).toHaveLength(3);
    expect(onAction).not.toHaveBeenCalled();

    // The compare action posts the verbatim action object (same reference).
    fireEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction).toHaveBeenCalledWith(root.actions[0]);
    expect(onAction.mock.calls[0]?.[0]).toBe(root.actions[0]);
  });

  it("wires per-card actions with the card's productId stamped into the payload", () => {
    const plan = parseFixture("product-grid-flights");
    const root = expectRoot(plan, "product_grid");
    const onAction = renderPlan(plan);

    const secondCard = screen.getAllByTestId("product-card")[1];
    fireEvent.click(within(secondCard).getByRole("button", { name: "Add to cart" }));
    expect(onAction).toHaveBeenCalledTimes(1);
    // Grid-level actions carry no productId; the clicked card stamps its own.
    expect(onAction.mock.calls[0]?.[0]).toEqual({
      ...root.actions[2],
      payload: { productId: root.props.productIds[1] },
    });
    expect(onAction.mock.calls[0]?.[0].type).toBe("add_to_cart");

    fireEvent.click(within(secondCard).getByRole("button", { name: "Details" }));
    expect(onAction).toHaveBeenCalledTimes(2);
    expect(onAction.mock.calls[1]?.[0]).toEqual({
      ...root.actions[1],
      payload: { productId: root.props.productIds[1] },
    });
  });
});

describe("PlanRenderer with the preference-picker fixture", () => {
  it("renders the question and two chips wired to their select_preference actions", () => {
    const plan = parseFixture("preference-picker-category");
    const root = expectRoot(plan, "preference_picker");
    const onAction = renderPlan(plan);

    expect(screen.getByTestId("plan-preference_picker")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Which category are you shopping for?",
      }),
    ).toBeInTheDocument();

    const chips = screen.getAllByTestId("action-select_preference");
    expect(chips).toHaveLength(2);

    const headphones = screen.getByRole("button", { name: "Headphones" });
    const other = screen.getByRole("button", { name: "Something else" });
    expect(headphones).toBeInTheDocument();
    expect(other).toBeInTheDocument();

    fireEvent.click(headphones);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0]?.[0]).toBe(root.actions[0]);

    fireEvent.click(other);
    expect(onAction).toHaveBeenCalledTimes(2);
    expect(onAction.mock.calls[1]?.[0]).toBe(root.actions[1]);
  });
});

describe("PlanRenderer with the comparison-table fixture", () => {
  it("renders two product columns, attribute rows, and the single choose CTA", () => {
    const plan = parseFixture("comparison-two");
    const root = expectRoot(plan, "comparison_table");
    const onAction = renderPlan(plan);

    expect(screen.getByTestId("plan-comparison_table")).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "aurora-hush-pro" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "cloudline-air" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("rowheader")).toHaveLength(5);
    expect(
      screen.getByRole("rowheader", { name: "price_usd" }),
    ).toBeInTheDocument();
    // Values come from the plan's optional values map (backend-rendered from
    // the catalog); booleans render yes/no, absent values as an em-dash.
    expect(screen.getByTestId("cell-aurora-hush-pro-price_usd")).toHaveTextContent("179");
    expect(screen.getByTestId("cell-aurora-hush-pro-comfort")).toHaveTextContent("4.7");
    expect(screen.getByTestId("cell-cloudline-air-anc_type")).toHaveTextContent("active");
    expect(screen.getByTestId("cell-cloudline-air-comfort")).toHaveTextContent("4.9");

    const choose = screen.getByRole("button", { name: "Choose Aurora Hush Pro" });
    fireEvent.click(choose);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0]?.[0]).toBe(root.actions[0]);
  });
});

describe("PlanRenderer with the product-details fixture", () => {
  it("renders the full detail card from the fixture snapshot", () => {
    const plan = parseFixture("product-details");
    expectRoot(plan, "product_details");
    const onAction = renderPlan(plan);

    expect(screen.getByTestId("plan-product_details")).toBeInTheDocument();
    expect(screen.getByText("Aurora Hush Pro")).toBeInTheDocument();
    expect(screen.getByText("aurora-hush-pro")).toBeInTheDocument();
    expect(screen.getByTestId("details-price")).toHaveTextContent("$179.00");
    expect(screen.getByText("adaptive")).toBeInTheDocument();
    expect(screen.getByText("What reviewers say")).toBeInTheDocument();
    expect(screen.getAllByTestId(/^quote-/)).toHaveLength(2);
    expect(screen.queryByTestId("quotes-placeholder")).not.toBeInTheDocument();
    expect(onAction).not.toHaveBeenCalled();
  });
});

describe("PlanRenderer with the cart-view fixture", () => {
  it("renders the item row, the formatted total, and the remove action", () => {
    const plan = parseFixture("cart-one-item");
    const root = expectRoot(plan, "cart_view");
    const onAction = renderPlan(plan);

    expect(screen.getByTestId("plan-cart_view")).toBeInTheDocument();
    const itemRow = screen.getByRole("row", { name: /aurora-hush-pro/ });
    expect(itemRow).toHaveAttribute("data-product-id", "aurora-hush-pro");
    expect(within(itemRow).getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("$179.00")).toBeInTheDocument();

    const remove = screen.getByRole("button", { name: "Remove" });
    fireEvent.click(remove);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0]?.[0]).toBe(root.actions[0]);
  });
});

describe("PlanRenderer with a synthetic text_block", () => {
  it("renders the optional heading and the body copy", () => {
    const raw = {
      planVersion: "1",
      sessionId: "session-1",
      turnId: 1,
      root: {
        type: "text_block",
        props: {
          heading: "How these were chosen",
          body: "Assumption: over-ear, travel-first, under $250.",
        },
        actions: [],
      },
    };
    const result = parseUiPlan(raw, CATALOG_IDS);
    if (!result.ok) {
      throw new Error(`synthetic plan failed the gate: ${result.errors.join("; ")}`);
    }
    const onAction = renderPlan(result.plan);

    expect(screen.getByTestId("plan-text_block")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "How these were chosen" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Assumption: over-ear, travel-first, under $250."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(onAction).not.toHaveBeenCalled();
  });
});

describe("PlanRenderer defensive floor", () => {
  it("renders the Pencil-tone notice for an unrecognized root type", () => {
    // The validation gate upstream makes this unreachable for wire data; the
    // hostile cast simulates a type slipping past every layer.
    const plan = parseFixture("product-details");
    const hostile = { ...plan, root: { ...plan.root, type: "video_player" } } as unknown as UiPlan;
    renderPlan(hostile);

    expect(screen.getByTestId("plan-unknown")).toBeInTheDocument();
    expect(screen.getByText("This result couldn't be displayed.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
