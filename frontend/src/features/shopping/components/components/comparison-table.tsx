"use client";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/shared/utils/cn";
import type {
  ComparisonTableProps,
  PlanAction,
} from "../../validations/plan-schema";

const HEADER_ACCENT = ["text-compare-1-fg", "text-compare-2-fg", "text-compare-3-fg"] as const;

const ATTRIBUTE_LABELS: Record<string, string> = {
  price_usd: "Price",
  battery_hours: "Battery",
  weight_g: "Weight",
  anc_type: "ANC",
  driver_mm: "Driver",
  comfort: "Comfort",
  anc: "ANC",
  sound: "Sound",
  battery: "Battery",
  value: "Value",
  multipoint: "Multipoint",
  folding: "Folding",
};

const LOWER_IS_BETTER = new Set(["price_usd", "weight_g"]);

function formatAttributeLabel(attribute: string): string {
  return ATTRIBUTE_LABELS[attribute] ?? attribute.replace(/_/g, " ");
}

function formatCellValue(
  value: string | number | boolean | null | undefined,
): string {
  if (value === undefined || value === null) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
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
    <section data-testid="plan-comparison_table" className="text-sm">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="h-8 w-28 px-2">
              <span className="sr-only">Attribute</span>
            </TableHead>
            {props.productIds.map((productId, index) => (
              <TableHead
                key={productId}
                data-product-id={productId}
                aria-label={productId}
                className={cn(
                  "h-8 px-2 font-mono text-xs font-medium",
                  HEADER_ACCENT[index % HEADER_ACCENT.length],
                  productId === recommendedProductId && "underline decoration-primary decoration-2",
                )}
              >
                {productId}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.attributes.map((attribute) => {
            const bestIds = bestProductIdsForAttribute(
              props.productIds,
              attribute,
              props.values,
            );

            return (
            <TableRow key={attribute}>
              <TableHead
                scope="row"
                aria-label={attribute}
                className="px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
              >
                {formatAttributeLabel(attribute)}
              </TableHead>
              {props.productIds.map((productId) => {
                const isBest = bestIds.has(productId);
                return (
                <TableCell
                  key={productId}
                  data-testid={`cell-${productId}-${attribute}`}
                  className={cn(
                    "px-2 py-2 font-mono text-xs tabular-nums",
                    isBest && "bg-success-bg font-semibold text-success-fg",
                  )}
                >
                  {formatCellValue(props.values?.[productId]?.[attribute])}
                  {isBest ? <span className="sr-only"> (best)</span> : null}
                </TableCell>
              );
              })}
            </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {chooseAction ? (
        <div className="mt-3">
          <Button
            size="sm"
            data-testid="action-choose"
            onClick={() => onAction(chooseAction)}
          >
            {chooseAction.label}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
