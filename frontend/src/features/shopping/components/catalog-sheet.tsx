"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { agentApiBaseUrl } from "@/shared/config/env";

import {
  fetchCatalog,
  type CatalogProduct,
  type CatalogResponse,
} from "../api/catalog-client";

/**
 * Catalog browse sheet (Curator's Desk): a drawer from the right listing the
 * full catalog — product name at Title weight, brand + category in Pencil,
 * the price in the tabular mono cut, a compact ANC chip where noise
 * cancellation exists, and one quiet "Ask about this" affordance per row that
 * hands the product back to the shell (which closes the sheet and sends the
 * question down the normal chat path).
 *
 * Fetch-on-open with `cache: "no-store"`; reopening aborts the previous
 * in-flight request via an AbortController ref. No virtualization — the
 * catalog is ~38 items.
 */

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const SKELETON_ROWS = [0, 1, 2, 3, 4, 5] as const;

type CatalogLoad =
  | { kind: "loading" }
  | { kind: "loaded"; data: CatalogResponse }
  | { kind: "error"; message: string };

export type CatalogSheetProps = {
  /** Props-driven open state; the parent owns it (fetch runs while open). */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Per-row affordance: the shell turns this into a chat turn. */
  onAskAbout?: (product: CatalogProduct) => void;
  /** Agent backend base URL; defaults to the shared env value. */
  baseUrl?: string;
};

export function CatalogSheet({
  open,
  onOpenChange,
  onAskAbout,
  baseUrl = agentApiBaseUrl,
}: CatalogSheetProps) {
  const [load, setLoad] = useState<CatalogLoad>({ kind: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  // Fetch on open; the cleanup aborts the in-flight request when the sheet
  // closes or is reopened (the next open mints a fresh controller). setState
  // runs only in the fetch continuations — never synchronously in the effect
  // body — and an aborted request never settles the UI.
  useEffect(() => {
    if (!open) {
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    fetchCatalog(baseUrl, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) {
          setLoad({ kind: "loaded", data });
        }
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoad({
            kind: "error",
            message:
              error instanceof Error
                ? error.message
                : "The catalog could not be loaded.",
          });
        }
      },
    );
    return () => {
      abortRef.current?.abort();
    };
  }, [open, baseUrl]);

  const handleRetry = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoad({ kind: "loading" });
    void fetchCatalog(baseUrl, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) {
          setLoad({ kind: "loaded", data });
        }
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setLoad({
            kind: "error",
            message:
              error instanceof Error
                ? error.message
                : "The catalog could not be loaded.",
          });
        }
      },
    );
  }, [baseUrl]);

  const handleAskAbout = useCallback(
    (product: CatalogProduct) => {
      onAskAbout?.(product);
      onOpenChange(false);
    },
    [onAskAbout, onOpenChange],
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {/*
        The shipped SheetContent anchors left by default; the className
        override (twMerge-resolved) moves the drawer to the right and sizes it
        for a comfortable product list.
      */}
      <SheetContent
        aria-label="Catalog"
        data-testid="catalog-sheet"
        className="left-auto right-0 flex w-full flex-col border-l border-r-0 sm:max-w-md"
      >
        <header className="flex items-baseline justify-between pr-8">
          <h2 className="text-lg font-semibold tracking-tight">Catalog</h2>
          {load.kind === "loaded" ? (
            <Label
              data-testid="catalog-count"
              className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground"
            >
              {load.data.count === 1
                ? "1 product"
                : `${load.data.count} products`}
            </Label>
          ) : null}
        </header>

        <div className="mt-4 flex-1 overflow-y-auto">
          {load.kind === "loading" ? (
            <div
              data-testid="catalog-loading"
              aria-hidden="true"
              className="space-y-3"
            >
              {SKELETON_ROWS.map((row) => (
                <Skeleton key={row} className="h-16 w-full" />
              ))}
            </div>
          ) : null}

          {load.kind === "loaded" ? (
            load.data.products.length === 0 ? (
              <p
                data-testid="catalog-empty"
                className="text-sm leading-[1.6] text-muted-foreground"
              >
                The catalog is empty.
              </p>
            ) : (
              <ul data-testid="catalog-list" className="divide-y">
                {load.data.products.map((product) => (
                  <li
                    key={product.id}
                    data-testid="catalog-row"
                    data-product-id={product.id}
                    className="py-3 first:pt-0 last:pb-0"
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-base font-medium leading-snug">
                        {product.name}
                      </p>
                      <span
                        data-testid="catalog-price"
                        className="shrink-0 font-mono text-sm tabular-nums"
                      >
                        {usd.format(product.priceUsd)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <p className="text-sm text-muted-foreground">
                        {product.brand} · {product.category}
                      </p>
                      {product.ancType !== "none" ? (
                        <Badge variant="secondary" data-testid="anc-badge">
                          ANC
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                      {product.id}
                    </p>
                    <div className="mt-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        data-testid="ask-about"
                        aria-label={`Ask about ${product.name}`}
                        onClick={() => handleAskAbout(product)}
                      >
                        Ask about this
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )
          ) : null}

          {load.kind === "error" ? (
            <div
              data-testid="catalog-error"
              role="status"
              className="rounded-lg border bg-secondary p-4 text-sm leading-[1.6] text-muted-foreground"
            >
              <p>{load.message}</p>
              <div className="mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="catalog-retry"
                  onClick={handleRetry}
                >
                  Retry
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
