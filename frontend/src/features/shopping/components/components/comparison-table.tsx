"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/shared/utils/cn";
import type {
  ComparisonTableProps,
  PlanAction,
} from "../../validations/plan-schema";

/** Per-column accent tokens (violet, coral, emerald) for up to three products. */
const COLUMN_STYLES = [
  {
    bar: "bg-compare-1",
    header: "bg-compare-1-bg text-compare-1-fg",
    dot: "bg-compare-1",
    cellBest: "bg-success-bg text-success-fg ring-1 ring-success/25",
  },
  {
    bar: "bg-compare-2",
    header: "bg-compare-2-bg text-compare-2-fg",
    dot: "bg-compare-2",
    cellBest: "bg-success-bg text-success-fg ring-1 ring-success/25",
  },
  {
    bar: "bg-compare-3",
    header: "bg-compare-3-bg text-compare-3-fg",
    dot: "bg-compare-3",
    cellBest: "bg-success-bg text-success-fg ring-1 ring-success/25",
  },
] as const;

const ATTRIBUTE_LABELS: Record<string, string> = {
  price_usd: "Price",
  battery_hours: "Battery",
  weight_g: "Weight",
  anc_type: "ANC",
  driver_mm: "Driver",
  comfort: "Comfort",
  anc: "ANC score",
  sound: "Sound",
  battery: "Battery score",
  value: "Value",
  multipoint: "Multipoint",
  folding: "Folding",
};

/** Lower-is-better for cost/weight; higher-is-better for scores and runtime. */
const LOWER_IS_BETTER = new Set(["price_usd", "weight_g"]);

function formatAttributeLabel(attribute: string): string {
  return (
    ATTRIBUTE_LABELS[attribute] ??
    attribute.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
  );
}

function formatCellValue(
  attribute: string,
  value: string | number | boolean | null | undefined,
): string {
  if (value === undefined || value === null) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "number") {
    if (attribute === "price_usd") {
      return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`;
    }
    if (attribute === "battery_hours") {
      return `${value}h`;
    }
    if (attribute === "weight_g") {
      return `${value}g`;
    }
    if (attribute === "driver_mm") {
      return `${value}mm`;
    }
    return String(value);
  }
  return String(value);
}

function numericValue(
  value: string | number | boolean | null | undefined,
): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? 1 : 0;
  }
  return null;
}

function bestProductIdsForAttribute(
  productIds: string[],
  attribute: string,
  values: ComparisonTableProps["values"],
): Set<string> {
  const scores = productIds
    .map((productId) => ({
      productId,
      value: numericValue(values?.[productId]?.[attribute]),
    }))
    .filter((entry): entry is { productId: string; value: number } => entry.value !== null);

  if (scores.length < 2) {
    return new Set();
  }

  const lowerIsBetter = LOWER_IS_BETTER.has(attribute);
  const target = lowerIsBetter
    ? Math.min(...scores.map((entry) => entry.value))
    : Math.max(...scores.map((entry) => entry.value));

  return new Set(
    scores.filter((entry) => entry.value === target).map((entry) => entry.productId),
  );
}

function formatProductId(productId: string): string {
  return productId
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export type ComparisonTableComponentProps = {
  props: ComparisonTableProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

export function ComparisonTable({
  props,
  actions,
  onAction,
}: ComparisonTableComponentProps) {
  const chooseAction = actions.find((action) => action.type === "choose");
  const recommendedProductId =
    chooseAction?.type === "choose" ? chooseAction.payload.productId : undefined;

  return (
    <section
      data-testid="plan-comparison_table"
      className="overflow-hidden rounded-xl border bg-card shadow-sm"
    >
      <div className="border-b bg-muted/40 px-4 py-3">
        <h2 className="text-sm font-semibold tracking-tight text-foreground">
          Side-by-side comparison
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Highlighted cells mark the strongest value in each row.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-36 border-b bg-muted/20 px-4 py-3 text-left">
                <span className="sr-only">Attribute</span>
              </th>
              {props.productIds.map((productId, columnIndex) => {
                const style = COLUMN_STYLES[columnIndex % COLUMN_STYLES.length];
                const isRecommended = productId === recommendedProductId;
                return (
                  <th
                    key={productId}
                    scope="col"
                    data-product-id={productId}
                    aria-label={productId}
                    className="border-b px-2 pb-0 pt-2 text-left align-bottom"
                  >
                    <div
                      className={cn(
                        "relative overflow-hidden rounded-t-lg px-3 py-3",
                        style.header,
                        isRecommended && "ring-2 ring-primary ring-offset-2 ring-offset-card",
                      )}
                    >
                      <div className={cn("absolute inset-x-0 top-0 h-1", style.bar)} />
                      <div className="flex items-start gap-2">
                        <span
                          className={cn("mt-1.5 size-2 shrink-0 rounded-full", style.dot)}
                          aria-hidden="true"
                        />
                        <div className="min-w-0">
                          <p className="truncate font-medium leading-snug">
                            {formatProductId(productId)}
                          </p>
                          <p className="mt-0.5 truncate font-mono text-[11px] opacity-80">
                            {productId}
                          </p>
                          {isRecommended ? (
                            <span className="mt-1.5 inline-flex rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary-foreground">
                              Pick
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {props.attributes.map((attribute, rowIndex) => {
              const bestIds = bestProductIdsForAttribute(
                props.productIds,
                attribute,
                props.values,
              );
              return (
                <tr
                  key={attribute}
                  className={cn(
                    "border-b last:border-b-0",
                    rowIndex % 2 === 0 ? "bg-background" : "bg-muted/15",
                  )}
                >
                  <th
                    scope="row"
                    aria-label={attribute}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground"
                  >
                    {formatAttributeLabel(attribute)}
                  </th>
                  {props.productIds.map((productId, columnIndex) => {
                    const style = COLUMN_STYLES[columnIndex % COLUMN_STYLES.length];
                    const rawValue = props.values?.[productId]?.[attribute];
                    const isBest = bestIds.has(productId);
                    const formatted = formatCellValue(attribute, rawValue);
                    const isBoolean = typeof rawValue === "boolean";

                    return (
                      <td
                        key={productId}
                        data-testid={`cell-${productId}-${attribute}`}
                        className="px-3 py-3 align-middle"
                      >
                        <span
                          className={cn(
                            "inline-flex min-w-[4.5rem] items-center justify-center rounded-md px-2.5 py-1.5 font-mono text-sm tabular-nums",
                            isBest && style.cellBest,
                            !isBest && isBoolean && rawValue === true && "bg-accent/15 text-accent",
                            !isBest && isBoolean && rawValue === false && "text-muted-foreground",
                            !isBest && !isBoolean && "text-foreground",
                          )}
                        >
                          {formatted}
                          {isBest ? (
                            <span className="sr-only"> (best)</span>
                          ) : null}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {chooseAction ? (
        <div className="border-t bg-muted/25 px-4 py-4">
          <Button
            data-testid="action-choose"
            className="w-full sm:w-auto"
            onClick={() => onAction(chooseAction)}
          >
            {chooseAction.label}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
