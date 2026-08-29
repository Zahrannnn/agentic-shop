"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/shared/components/layout/page-header";
import { metrics } from "../constants/metrics";
import { useDashboardWorkItems } from "../hooks/use-dashboard-work-items";
import { MetricCard } from "./MetricCard";
import { PreferencePanel } from "./PreferencePanel";
import { WorkItemsTable } from "./WorkItemsTable";

export function DashboardPage() {
  const workItems = useDashboardWorkItems();

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Starter product surface showing metrics, server-state, table logic, and client preferences."
      />
      <section className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>
      <section className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader>
            <CardTitle>Work items</CardTitle>
          </CardHeader>
          <CardContent>
            {workItems.isPending ? (
              <Skeleton className="h-56 w-full" />
            ) : workItems.isError ? (
              <p className="text-sm text-destructive">Unable to load work items.</p>
            ) : (
              <WorkItemsTable data={workItems.data} />
            )}
          </CardContent>
        </Card>
        <PreferencePanel />
      </section>
    </>
  );
}
