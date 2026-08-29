import type { WorkItem } from "../types";

const workItems: WorkItem[] = [
  {
    id: "CORE-101",
    name: "Feature scaffold",
    owner: "Frontend",
    status: "Healthy",
    updatedAt: "2026-07-06T10:30:00.000Z",
  },
  {
    id: "CORE-102",
    name: "REST client contract",
    owner: "Platform",
    status: "Watch",
    updatedAt: "2026-07-06T11:15:00.000Z",
  },
  {
    id: "CORE-103",
    name: "Docker runtime",
    owner: "DevOps",
    status: "Blocked",
    updatedAt: "2026-07-06T12:00:00.000Z",
  },
];

export async function getDashboardWorkItems() {
  await new Promise((resolve) => setTimeout(resolve, 250));
  return workItems;
}
