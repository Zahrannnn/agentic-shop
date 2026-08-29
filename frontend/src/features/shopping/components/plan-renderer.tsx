"use client";

import type { PlanAction, UiPlan } from "../validations/plan-schema";
import { CartView } from "./components/cart-view";
import { ComparisonTable } from "./components/comparison-table";
import { PreferencePicker } from "./components/preference-picker";
import { ProductDetails } from "./components/product-details";
import { ProductGrid } from "./components/product-grid";
import { TextBlock } from "./components/text-block";

/**
 * Plan renderer (registry semantics per FRONTEND_GUIDE.md §5). Accepts an
 * ALREADY-VALIDATED `UiPlan` — the hook layer runs `parseUiPlan` (the Zod
 * gate) before anything reaches this component, so unknown or invalid
 * component types never arrive here. The switch below is the fixed registry:
 * one entry per contracted type, no fallback rendering of unknown types.
 *
 * Every interactive component posts its action object verbatim through
 * `onAction`; nothing is resolved or rewritten client-side.
 */
export type OnPlanAction = (action: PlanAction) => void;

export type PlanRendererProps = {
  plan: UiPlan;
  onAction: OnPlanAction;
};

export function PlanRenderer({ plan, onAction }: PlanRendererProps) {
  const root = plan.root;

  switch (root.type) {
    case "product_grid":
      return (
        <ProductGrid
          props={root.props}
          actions={root.actions}
          onAction={onAction}
        />
      );
    case "preference_picker":
      return (
        <PreferencePicker
          props={root.props}
          actions={root.actions}
          onAction={onAction}
        />
      );
    case "comparison_table":
      return (
        <ComparisonTable
          props={root.props}
          actions={root.actions}
          onAction={onAction}
        />
      );
    case "product_details":
      return <ProductDetails props={root.props} />;
    case "cart_view":
      return (
        <CartView props={root.props} actions={root.actions} onAction={onAction} />
      );
    case "text_block":
      return <TextBlock props={root.props} />;
    default:
      // Defensive floor only: the validation gate upstream makes this branch
      // unreachable for wire data. A quiet Pencil-tone notice — never a crash,
      // never a guess at rendering an uncontracted type.
      return (
        <p
          role="status"
          data-testid="plan-unknown"
          className="rounded-lg border bg-card p-4 text-sm text-muted-foreground"
        >
          This result couldn&apos;t be displayed.
        </p>
      );
  }
}
