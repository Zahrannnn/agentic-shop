"use client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/shared/components/feedback/empty-state";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <EmptyState
        title="Something went wrong"
        description="The route could not finish rendering. Try again or check the console for details."
        action={<Button onClick={reset}>Try again</Button>}
      />
    </main>
  );
}
