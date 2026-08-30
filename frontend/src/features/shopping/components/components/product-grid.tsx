"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/shared/utils/cn";
import type { PlanAction, ProductGridProps } from "../../validations/plan-schema";

/**
 * Ranked product grid (Curator's Desk, ecommerce register): each card is a
 * flat Paper tile with the product name as its title, the price in the mono
 * tabular cut, an ANC badge when the product actually cancels noise, and the
 * mono catalog id beneath — the card's provenance. The only Teal Ink on the
 * view is the underline on the top-ranked product — the agent's commitment
 * (One Underline).
 *
 * Cards render from the optional `products` snapshot when the backend provides
 * it; a plan without the snapshot degrades to the mono-id card.
 */
export type ProductGridComponentProps = {
  props: ProductGridProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

const rankLabel = (index: number): string => String(index + 1).padStart(2, "0");

const RANK_ACCENT = [
  "bg-compare-1 text-white",
  "bg-compare-2 text-white",
  "bg-compare-3 text-white",
] as const;

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
  const snapshot = new Map((props.products ?? []).map((product) => [product.id, product]));

  return (
    <section data-testid="plan-product_grid">
      <h2 className="text-xl font-semibold tracking-tight">{props.title}</h2>
      <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {props.productIds.map((productId, index) => {
          const recommended = props.ranked && index === 0;
          const product = snapshot.get(productId);
          return (
            <li
              key={productId}
              data-testid="product-card"
              data-product-id={productId}
              className={cn(
                "flex flex-col gap-3 rounded-lg border bg-card p-4 transition-colors",
                recommended && "border-primary/40 bg-primary/[0.03] shadow-sm",
              )}
            >
              <div className="flex items-center justify-between">
                {props.ranked ? (
                  <span
                    className={cn(
                      "inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold tabular-nums",
                      RANK_ACCENT[index % RANK_ACCENT.length],
                    )}
                  >
                    {rankLabel(index)}
                  </span>
                ) : (
                  <span />
                )}
                {product && product.ancType !== "none" ? (
                  <Badge variant="secondary" className="uppercase">
                    {product.ancType} ANC
                  </Badge>
                ) : null}
              </div>

              <div>
                <p
                  className={cn(
                    "text-base font-medium leading-snug",
                    recommended && "underline decoration-primary decoration-2 underline-offset-4",
                  )}
                >
                  {product?.name ?? productId}
                </p>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">{productId}</p>
              </div>

              {product ? (
                <p
                  data-testid={`price-${productId}`}
                  className="font-mono text-lg tabular-nums text-foreground"
                >
                  ${product.priceUsd.toFixed(2)}
                </p>
              ) : null}

              {detailsAction || addToCartAction ? (
                <div className="mt-auto flex flex-wrap gap-2">
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
