"use client";

import { format } from "date-fns";
import { Activity, AlertTriangle, CheckCircle2, CircleSlash } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/shared/components/layout/page-header";
import { useHealthStatus } from "../hooks/use-health-status";
import type { HealthStatus } from "../types";

const statusIcon: Record<HealthStatus, typeof CheckCircle2> = {
  reachable: CheckCircle2,
  unreachable: AlertTriangle,
  missing: CircleSlash,
};

const statusVariant: Record<HealthStatus, "success" | "warning" | "destructive"> = {
  reachable: "success",
  unreachable: "destructive",
  missing: "warning",
};

export function HealthPage() {
  const health = useHealthStatus();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 p-4 md:p-6">
      <PageHeader
        title="Health"
        description="Public status check for external REST backends configured in the environment."
      />
      {health.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : health.isError ? (
        <Card>
          <CardContent className="p-6 text-sm text-destructive">
            Unable to load health checks.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              Backend services
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Checked {format(new Date(health.data.checkedAt), "PPpp")}
            </p>
          </CardHeader>
          <CardContent className="grid gap-3">
            {health.data.services.map((service) => {
              const Icon = statusIcon[service.status];

              return (
                <div
                  key={service.key}
                  className="grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <h2 className="text-sm font-semibold">{service.label}</h2>
                    </div>
                    {service.url ? (
                      <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                        {service.url}
                      </p>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">
                        No URL configured.
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={statusVariant[service.status]}>
                      {service.status}
                    </Badge>
                    {service.latencyMs !== null ? (
                      <span className="text-xs text-muted-foreground">
                        {service.latencyMs}ms
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
