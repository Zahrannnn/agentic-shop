import type { InputHTMLAttributes } from "react";
import { cn } from "@/shared/utils/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
