"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/shared/utils/cn";
import type { PlanAction, ProductGridProps } from "../../validations/plan-schema";

/**
 * Ranked product grid (Curator's Desk): the title is the Headline, every row
 * is a flat Paper card behind a hairline, and the only Teal Ink on the view is
 * the underline on the top-ranked id — the agent's commitment (One Underline).
 *
 * The wire contract carries ids only (no names, no prices), so the catalog id
 * stands in as the product identifier, set in the mono cut.
 */
export type ProductGridComponentProps = {
  props: ProductGridProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

const rankLabel = (index: number): string => String(index + 1).padStart(2, "0");

/** Per-card dispatch: grid-level actions carry no productId (the wire
 * contract defines them once per grid), so the card that was clicked stamps
 * its own product into the payload before the action reaches the agent. */
function withProduct(action: PlanAction, productId: string): PlanAction {
  return { ...action, payload: { ...action.payload, productId } };
}

export function ProductGrid({ props, actions, onAction }: ProductGridComponentProps) {
  // One button per unique action type: details/add_to_cart attach to every
  // card, compare is a single grid-level control. Actions post verbatim —
  // positional resolution happens server-side, never here.
  const compareAction = actions.find((action) => action.type === "compare");
  const detailsAction = actions.find((action) => action.type === "details");
  const addToCartAction = actions.find((action) => action.type === "add_to_cart");

  return (
    <section data-testid="plan-product_grid">
      <h2 className="text-xl font-semibold tracking-tight">{props.title}</h2>
      <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {props.productIds.map((productId, index) => {
          const recommended = props.ranked && index === 0;
          return (
            <li
              key={productId}
              data-testid="product-card"
              data-product-id={productId}
              className="rounded-lg border bg-card p-4"
            >
              {props.ranked ? (
                <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
                  {rankLabel(index)}
                </p>
              ) : null}
              <p
                className={cn(
                  "font-mono text-sm leading-relaxed",
                  recommended &&
                    "underline decoration-primary decoration-2 underline-offset-4",
                )}
              >
                {productId}
              </p>
              {detailsAction || addToCartAction ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {detailsAction ? (
                    <Button
                      variant="outline"
                      size="sm"
                      data-testid="action-details"
                      onClick={() => onAction(withProduct(detailsAction, productId))}
                    >
                      {detailsAction.label}
                    </Button>
                  ) : null}
                  {addToCartAction ? (
                    <Button
                      variant="outline"
                      size="sm"
                      data-testid="action-add_to_cart"
                      onClick={() => onAction(withProduct(addToCartAction, productId))}
                    >
                      {addToCartAction.label}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      {compareAction ? (
        <div className="mt-4">
          <Button
            variant="outline"
            size="sm"
            data-testid="action-compare"
            onClick={() => onAction(compareAction)}
          >
            {compareAction.label}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
