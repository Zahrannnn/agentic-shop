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
import type {
  ComparisonTableProps,
  PlanAction,
} from "../../validations/plan-schema";

/**
 * Side-by-side comparison (Curator's Desk): product columns carry mono id
 * headers, attribute rows carry Label-style uppercase row headers, and every
 * value cell aligns in the mono tabular cut (The Numerals Rule). Values come
 * from the plan's optional `values` map (backend-rendered from the catalog);
 * cells without a value hold a Pencil em-dash. The single `choose` action
 * renders as the one primary (Teal Ink) control below the table: the agent's
 * commitment.
 */
/**
 * Format one comparison cell: booleans as yes/no, missing values as an
 * em-dash; numbers and strings render verbatim (tabular mono alignment).
 */
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

  return (
    <section data-testid="plan-comparison_table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">
              <span className="sr-only">Attribute</span>
            </TableHead>
            {props.productIds.map((productId) => (
              <TableHead
                key={productId}
                data-product-id={productId}
                className="font-mono text-sm font-medium text-foreground"
              >
                {productId}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.attributes.map((attribute) => (
            <TableRow key={attribute}>
              <TableHead
                scope="row"
                className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground"
              >
                {attribute}
              </TableHead>
              {props.productIds.map((productId) => (
                <TableCell
                  key={productId}
                  data-testid={`cell-${productId}-${attribute}`}
                  className="font-mono tabular-nums text-foreground"
                >
                  {formatCellValue(props.values?.[productId]?.[attribute])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {chooseAction ? (
        <div className="mt-4">
          <Button data-testid="action-choose" onClick={() => onAction(chooseAction)}>
            {chooseAction.label}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
