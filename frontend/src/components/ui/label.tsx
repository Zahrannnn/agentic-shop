import * as LabelPrimitive from "@radix-ui/react-label";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/utils/cn";

export function Label({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn("text-sm font-medium leading-none", className)}
      {...props}
    />
  );
}
