"use client";

import { Button } from "@/components/ui/button";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
          <div className="max-w-md space-y-4 text-center">
            <h1 className="text-2xl font-semibold">The app crashed</h1>
            <p className="text-sm text-muted-foreground">
              This is the final safety net. Route-level errors should handle
              most recoverable failures before this screen appears.
            </p>
            <Button onClick={reset}>Reload</Button>
          </div>
        </main>
      </body>
    </html>
  );
}
