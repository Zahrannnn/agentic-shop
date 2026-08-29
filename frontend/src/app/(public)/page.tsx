import { Suspense } from "react";
import {
  CachedBoilerplatePrinciples,
  DynamicBuildSignal,
  WelcomePage,
} from "@/features/welcome";
import { Skeleton } from "@/components/ui/skeleton";

export const unstable_instant = {
  prefetch: "static",
};

export default function Page() {
  return (
    <WelcomePage
      cachedDemo={<CachedBoilerplatePrinciples />}
      dynamicDemo={
        <Suspense fallback={<Skeleton className="h-24 w-full" />}>
          <DynamicBuildSignal />
        </Suspense>
      }
    />
  );
}
