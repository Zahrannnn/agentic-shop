"use client";

import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/shared/utils/cn";
import type { ProductDetailsProps } from "../../validations/plan-schema";

/**
 * Product detail card (Curator's Desk, D12 evidence edition): the price is
 * THE number (hero position, no duplicate spec row), attributes align in a
 * two-column Label/mono grid, and the review scores render as fine tick
 * scales (The Numerals Rule — an instrument, not a SaaS progress bar).
 *
 * The evidence link (overdrive): hovering or focusing a score dims every
 * quote that does not discuss that attribute, and hovering a quote dims the
 * scores it does not back — the agent's "every reason cites a checkable
 * number" promise made physical. Matching is deterministic keyword lookup
 * over the quote text; keyboard focus drives the same state as hover;
 * reduced-motion users get opacity-only shifts (the only transition used).
 *
 * All snapshot fields are optional — a minimal plan degrades to the id-only
 * card. This component takes no actions (the contract allows none).
 */
export type ProductDetailsComponentProps = {
  props: ProductDetailsProps;
  /** D10: when true, the title/price carry view-transition names for the grid→detail morph. */
  named?: boolean;
};

type ScoreKey = "comfort" | "anc" | "sound" | "battery" | "value";

const SCORE_LABELS: Record<ScoreKey, string> = {
  comfort: "Comfort",
  anc: "Noise cancelling",
  sound: "Sound",
  battery: "Battery",
  value: "Value",
};

/** Deterministic quote↔attribute matching: which keywords evidence which score. */
const SCORE_EVIDENCE: Record<ScoreKey, string[]> = {
  comfort: ["comfort", "pad", "wear", "warm", "clamp", "fit", "light"],
  anc: ["anc", "noise", "rumble", "subway", "isolation", "quiet", "wind", "cabin"],
  sound: ["sound", "audio", "bass", "treble", "balanced", "music", "acoustic", "electronic"],
  battery: ["battery", "charge", "hour", "playback", "week"],
  value: ["value", "price", "cheap", "deal", "worth", "cost", "$", "above its price"],
};

function matchesScore(quote: string, key: ScoreKey): boolean {
  const lowered = quote.toLowerCase();
  return SCORE_EVIDENCE[key].some((needle) => lowered.includes(needle));
}

function formatAttribute(
  label: string,
  value: string | number | boolean | undefined,
  unit?: string,
): { label: string; value: string } | null {
  if (value === undefined || value === "") {
    return null;
  }
  if (typeof value === "boolean") {
    return { label, value: value ? "yes" : "no" };
  }
  return { label, value: `${value}${unit ? ` ${unit}` : ""}` };
}

export function ProductDetails({ props, named = false }: ProductDetailsComponentProps) {
  const [activeScore, setActiveScore] = useState<ScoreKey | null>(null);
  const [activeQuote, setActiveQuote] = useState<number | null>(null);

  const productId = props.productId;
  // Shares the grid card's morph identity: same name in the old and new
  // snapshots is what makes the View Transition move the card into the
  // detail header.
  const morphName = named && productId ? { viewTransitionName: `product-${productId}` } : undefined;

  const attributes = [
    formatAttribute("Battery", props.batteryHours, "h"),
    formatAttribute("Weight", props.weightG, "g"),
    formatAttribute("ANC", props.ancType),
    formatAttribute("Driver", props.driverMm, "mm"),
    formatAttribute("Codecs", props.codecs?.join(", ")),
    formatAttribute("Multipoint", props.multipoint),
    formatAttribute("Folding", props.folding),
  ].filter((entry): entry is { label: string; value: string } => entry !== null);

  const scores = props.reviewScores
    ? (Object.entries(props.reviewScores) as [ScoreKey, number][])
    : [];

  const quotes = props.showQuotes && props.quotes ? props.quotes : [];
  const quoteMatches = (index: number, key: ScoreKey): boolean =>
    quotes[index] !== undefined && matchesScore(quotes[index], key);

  return (
    <Card data-testid="plan-product_details" className="shadow-none">
      <CardContent className="grid gap-4 p-5 sm:grid-cols-[1fr_auto] sm:items-start sm:gap-6">
        <div className="space-y-1.5">
          <h2
            className="text-2xl font-semibold tracking-tight"
            style={morphName}
          >
            {props.productName ?? props.productId}
          </h2>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono text-xs">{props.productId}</span>
            {props.brand ? (
              <>
                <span aria-hidden="true" className="text-border">
                  ·
                </span>
                <span>{props.brand}</span>
              </>
            ) : null}
          </p>
        </div>
        {props.priceUsd !== undefined ? (
          <p
            data-testid="details-price"
            className="font-mono text-3xl tabular-nums tracking-tight sm:justify-self-end"
          >
            ${props.priceUsd.toFixed(2)}
          </p>
        ) : null}
      </CardContent>

      <CardContent className="grid gap-8 border-t pt-5 sm:grid-cols-[1fr_auto] sm:gap-10">
        {attributes.length > 0 ? (
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:max-w-md">
            {attributes.map((entry) => (
              <div key={entry.label} className="space-y-0.5">
                <dt className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
                  {entry.label}
                </dt>
                <dd className="font-mono text-sm tabular-nums">{entry.value || "—"}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        {scores.length > 0 ? (
          <div
            role="group"
            aria-label="Reviewer scores"
            className={cn(
              "space-y-3 self-start sm:w-56",
              activeQuote !== null && "opacity-90",
            )}
          >
            <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
              Reviewer scores
            </p>
            {scores.map(([key, value]) => {
              const isActive = activeScore === key;
              const isBacked = activeQuote === null || quoteMatches(activeQuote, key);
              const filled = Math.round(value);
              return (
                <div
                  key={key}
                  tabIndex={0}
                  role="img"
                  aria-label={`${SCORE_LABELS[key]} ${value.toFixed(1)} out of 5`}
                  data-testid={`score-${key}`}
                  onMouseEnter={() => setActiveScore(key)}
                  onMouseLeave={() => setActiveScore(null)}
                  onFocus={() => setActiveScore(key)}
                  onBlur={() => setActiveScore(null)}
                  className={cn(
                    "cursor-default rounded-sm px-1 py-0.5 transition-opacity duration-200",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                    isBacked ? "opacity-100" : "opacity-30",
                    isActive && "bg-muted",
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
                      {SCORE_LABELS[key] ?? key}
                    </span>
                    <span className="font-mono text-sm tabular-nums">
                      {value.toFixed(1)}
                    </span>
                  </div>
                  <div className="mt-1 flex gap-1" aria-hidden="true">
                    {Array.from({ length: 5 }, (_, tick) => (
                      <span
                        key={tick}
                        className={cn(
                          "h-1 flex-1 rounded-[1px]",
                          tick < filled
                            ? "bg-foreground/70"
                            : "bg-border",
                        )}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </CardContent>

      {quotes.length > 0 ? (
        <CardContent className="border-t pt-5">
          <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
            What reviewers say
          </p>
          <ul className="mt-3 max-w-prose space-y-3">
            {quotes.map((quote, index) => {
              const backing = quoteBackingScores(quote);
              const matchesActive =
                activeScore === null || backing.includes(activeScore);
              return (
                <li
                  key={index}
                  data-testid={`quote-${index}`}
                  tabIndex={0}
                  onMouseEnter={() => setActiveQuote(index)}
                  onMouseLeave={() => setActiveQuote(null)}
                  onFocus={() => setActiveQuote(index)}
                  onBlur={() => setActiveQuote(null)}
                  className={cn(
                    "rounded-sm px-1 py-0.5 text-sm italic leading-[1.6] transition-opacity duration-200",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                    matchesActive
                      ? "text-foreground"
                      : "text-muted-foreground opacity-35",
                  )}
                >
                  “{quote}”
                </li>
              );
            })}
          </ul>
        </CardContent>
      ) : null}
    </Card>
  );
}

/** Score keys whose evidence keywords appear in the quote. */
function quoteBackingScores(quote: string): ScoreKey[] {
  return (Object.keys(SCORE_EVIDENCE) as ScoreKey[]).filter((key) =>
    matchesScore(quote, key),
  );
}
