"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardWorkItems } from "../api/dashboard-adapter";

export function useDashboardWorkItems() {
  return useQuery({
    queryKey: ["dashboard", "work-items"],
    queryFn: getDashboardWorkItems,
  });
}
