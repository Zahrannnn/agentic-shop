import type { TextareaHTMLAttributes } from "react";
import { cn } from "@/shared/utils/cn";

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
