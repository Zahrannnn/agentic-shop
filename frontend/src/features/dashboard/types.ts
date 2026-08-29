export type Metric = {
  label: string;
  value: string;
  trend: string;
};

export type WorkItem = {
  id: string;
  name: string;
  owner: string;
  status: "Healthy" | "Watch" | "Blocked";
  updatedAt: string;
};

export type MetricCardProps = {
  metric: Metric;
};
