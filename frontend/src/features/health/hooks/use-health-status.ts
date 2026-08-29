"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealthStatus } from "../api/health-client";

export function useHealthStatus() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealthStatus,
    refetchInterval: 30_000,
  });
}
