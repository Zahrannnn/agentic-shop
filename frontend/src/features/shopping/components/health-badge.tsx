"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";

import { agentApiBaseUrl } from "@/shared/config/env";

/**
 * Backend-mode badge (US5): fetches the agent backend's `GET /health` once on
 * mount and shows which mode it is talking to — "mock" (deterministic, no
 * network) in a muted Desk tone, "real" in Teal Ink, and "offline" in Pencil
 * when the endpoint is unreachable. A quiet Label chip; never a crash, never
 * a spinner.
 */

type HealthPayload = { mode?: unknown };

export type HealthBadgeMode = "loading" | "mock" | "real" | "offline";

const BADGE_LABELS: Record<Exclude<HealthBadgeMode, "loading">, string> = {
  mock: "MOCK",
  real: "REAL",
  offline: "OFFLINE",
};

export function HealthBadge() {
  const [mode, setMode] = useState<HealthBadgeMode>("loading");

  useEffect(() => {
    let cancelled = false;

    fetch(`${agentApiBaseUrl}/health`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`health check failed (HTTP ${response.status})`);
        }
        return (await response.json()) as HealthPayload;
      })
      .then((payload) => {
        if (payload.mode !== "mock" && payload.mode !== "real") {
          throw new Error("health check reported no known mode");
        }
        if (!cancelled) {
          setMode(payload.mode);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMode("offline");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (mode === "loading") {
    // shadcn Skeleton placeholder while the health check resolves.
    return (
      <Skeleton
        data-testid="health-badge"
        aria-hidden="true"
        className="inline-flex h-6 w-14 items-center rounded-md"
      />
    );
  }

  return (
    <span
      role="status"
      data-testid="health-badge"
      data-mode={mode}
      className={
        mode === "real"
          ? "inline-flex items-center rounded-md bg-primary px-2 py-1 text-xs font-medium uppercase tracking-[0.05em] text-primary-foreground"
          : mode === "mock"
            ? "inline-flex items-center rounded-md bg-secondary px-2 py-1 text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground"
            : "inline-flex items-center rounded-md border bg-transparent px-2 py-1 text-xs font-medium uppercase tracking-[0.05em] text-muted-foreground"
      }
    >
      {BADGE_LABELS[mode]}
    </span>
  );
}
