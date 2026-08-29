import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProductDetailsProps } from "../../validations/plan-schema";

/**
 * Product detail card (Curator's Desk): the catalog id is the title, set in
 * the mono cut (names are not in the wire contract). When `showQuotes` is set
 * the quotes area renders as a skeleton placeholder — quote content is not in
 * the props, and the placeholder keeps the layout honest instead of inventing
 * copy. This component takes no actions (the contract allows none).
 */
export type ProductDetailsComponentProps = {
  props: ProductDetailsProps;
};

export function ProductDetails({ props }: ProductDetailsComponentProps) {
  return (
    <Card data-testid="plan-product_details" className="shadow-none">
      <CardContent className="p-5">
        <h2 className="font-mono text-base font-medium">{props.productId}</h2>
        {props.showQuotes ? (
          <div className="mt-4" data-testid="quotes-placeholder">
            <p className="text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground">
              Quotes
            </p>
            <div className="mt-2 max-w-prose space-y-2" aria-hidden="true">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
