import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MetricCardProps } from "../types";

export function MetricCard({ metric }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">{metric.label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold">{metric.value}</p>
        <p className="mt-1 text-sm text-muted-foreground">{metric.trend}</p>
      </CardContent>
    </Card>
  );
}
