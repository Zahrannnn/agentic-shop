"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/utils/cn";

export const Tabs = TabsPrimitive.Root;

export function TabsList({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex h-10 items-center rounded-md bg-muted p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex items-center justify-center rounded-sm px-3 py-1.5 text-sm font-medium data-[state=active]:bg-background data-[state=active]:shadow-sm",
        className
      )}
      {...props}
    />
  );
}

export const TabsContent = TabsPrimitive.Content;
