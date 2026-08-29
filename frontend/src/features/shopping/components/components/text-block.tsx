import { cn } from "@/shared/utils/cn";
import type { TextBlockProps } from "../../validations/plan-schema";

/**
 * Disclosure/notice block (Curator's Desk): a recessed Desk-tone panel behind
 * a hairline — the quietest surface in the system, matching its role as the
 * agent's assumptions and side notes. Optional Headline, body at the Body
 * measure (65–75ch, 1.6 line-height). This component takes no actions (the
 * contract allows none).
 */
export type TextBlockComponentProps = {
  props: TextBlockProps;
};

export function TextBlock({ props }: TextBlockComponentProps) {
  return (
    <section data-testid="plan-text_block" className="rounded-lg border bg-muted p-4">
      {props.heading ? (
        <h2 className="text-xl font-semibold tracking-tight">{props.heading}</h2>
      ) : null}
      <p
        className={cn(
          "max-w-prose text-[15px] leading-[1.6]",
          props.heading && "mt-2",
        )}
      >
        {props.body}
      </p>
    </section>
  );
}
