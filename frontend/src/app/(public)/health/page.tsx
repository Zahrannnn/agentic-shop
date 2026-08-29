import type { Metadata } from "next";
import { HealthPage } from "@/features/health";

export const metadata: Metadata = {
  title: "Health",
  description: "Public backend health check view.",
};

export default function Page() {
  return <HealthPage />;
}
