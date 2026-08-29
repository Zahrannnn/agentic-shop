export type HealthStatus = "reachable" | "unreachable" | "missing";

export type HealthService = {
  key: string;
  label: string;
  url?: string;
  status: HealthStatus;
  latencyMs: number | null;
};

export type HealthResponse = {
  checkedAt: string;
  services: HealthService[];
};
