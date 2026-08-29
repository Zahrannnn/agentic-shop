import type { HealthResponse } from "../types";

export async function getHealthStatus() {
  const response = await fetch("/api/health", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Health check failed.");
  }

  return (await response.json()) as HealthResponse;
}
