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
import type { CartViewProps, PlanAction } from "../../validations/plan-schema";

/**
 * Cart summary (Curator's Desk): a flat table of mono item ids and tabular
 * quantities, closed by a "Total" footer row. Line prices are not in the wire
 * contract, so no price column exists — only `totalUsd`, rendered in the mono
 * tabular cut (The Numerals Rule). Each item carries its matching
 * `remove_from_cart` action, dispatched verbatim.
 */
export type CartViewComponentProps = {
  props: CartViewProps;
  actions: PlanAction[];
  onAction: (action: PlanAction) => void;
};

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function CartView({ props, actions, onAction }: CartViewComponentProps) {
  return (
    <section data-testid="plan-cart_view">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead className="text-right">Quantity</TableHead>
            <TableHead className="text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.items.map((item) => {
            const removeAction = actions.find(
              (action) =>
                action.type === "remove_from_cart" &&
                action.payload.productId === item.productId,
            );
            return (
              <TableRow key={item.productId} data-product-id={item.productId}>
                <TableCell className="font-mono text-sm">{item.productId}</TableCell>
                <TableCell className="text-right font-mono tabular-nums">
                  {item.quantity}
                </TableCell>
                <TableCell className="text-right">
                  {removeAction ? (
                    <Button
                      variant="outline"
                      size="sm"
                      data-testid="action-remove_from_cart"
                      onClick={() => onAction(removeAction)}
                    >
                      {removeAction.label}
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            );
          })}
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={2}
              className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground"
            >
              Total
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {usd.format(props.totalUsd)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  );
}
