import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ProductDetailsProps } from "../../validations/plan-schema";

/**
 * Product detail card (Curator's Desk): the catalog name is the title, the id
 * rides beneath it in the mono cut, the price is the one prominent number,
 * attributes align in a Label/mono grid (The Numerals Rule), review scores
 * render as quiet chips, and reviewer quotes appear when the agent flagged
 * `showQuotes`. All snapshot fields are optional — a minimal plan degrades to
 * the id-only card. This component takes no actions (the contract allows
 * none).
 */
export type ProductDetailsComponentProps = {
  props: ProductDetailsProps;
};

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

export function ProductDetails({ props }: ProductDetailsComponentProps) {
  const hasSnapshot = props.productName !== undefined;
  const attributes = [
    formatAttribute("Price", props.priceUsd !== undefined ? `$${props.priceUsd.toFixed(2)}` : undefined),
    formatAttribute("Battery", props.batteryHours, "h"),
    formatAttribute("Weight", props.weightG, "g"),
    formatAttribute("ANC", props.ancType),
    formatAttribute("Driver", props.driverMm, "mm"),
    formatAttribute("Codecs", props.codecs?.join(", ")),
    formatAttribute("Multipoint", props.multipoint),
    formatAttribute("Folding", props.folding),
  ].filter((entry): entry is { label: string; value: string } => entry !== null);

  const scores = props.reviewScores
    ? (Object.entries(props.reviewScores) as [string, number][])
    : [];

  return (
    <Card data-testid="plan-product_details" className="shadow-none">
      <CardContent className="grid gap-6 p-5 sm:grid-cols-[1fr_auto] sm:items-start">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold tracking-tight">
            {props.productName ?? props.productId}
          </h2>
          <p className="font-mono text-sm text-muted-foreground">{props.productId}</p>
          {props.brand ? (
            <p className="text-sm text-muted-foreground">{props.brand}</p>
          ) : null}
        </div>
        {props.priceUsd !== undefined ? (
          <p
            data-testid="details-price"
            className="font-mono text-xl tabular-nums sm:justify-self-end"
          >
            ${props.priceUsd.toFixed(2)}
          </p>
        ) : null}
      </CardContent>
      <CardContent className="grid gap-6 pt-0 sm:grid-cols-2">
        {attributes.length > 0 ? (
          <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-6 gap-y-2 sm:col-span-1">
            {attributes.map((entry) => (
              <div key={entry.label} className="col-span-2 grid grid-cols-subgrid">
                <dt className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
                  {entry.label}
                </dt>
                <dd className="text-right font-mono text-sm tabular-nums">
                  {entry.value || "—"}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
        {scores.length > 0 ? (
          <div className="flex flex-wrap items-start gap-1.5 sm:justify-end">
            {scores.map(([label, value]) => (
              <Badge key={label} variant="secondary" className="font-mono tabular-nums">
                {label} {value.toFixed(1)}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
      {props.showQuotes && props.quotes && props.quotes.length > 0 ? (
        <CardContent className="pt-0">
          <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
            What reviewers say
          </p>
          <ul className="mt-3 max-w-prose space-y-3">
            {props.quotes.map((quote, index) => (
              <li
                key={index}
                data-testid={`quote-${index}`}
                className="border-l-0 pl-0 text-sm italic leading-[1.6] text-muted-foreground"
              >
                “{quote}”
              </li>
            ))}
          </ul>
        </CardContent>
      ) : null}
    </Card>
  );
}
