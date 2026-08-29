import { NextResponse } from "next/server";
import { backendServices, env } from "@/shared/config/env";

export async function GET() {
  const results = await Promise.all(
    backendServices.map(async (service) => {
      if (!service.baseUrl) {
        return {
          key: service.key,
          label: service.label,
          url: env.NEXT_PUBLIC_SHOW_HEALTH_URLS ? "" : undefined,
          status: "missing" as const,
          latencyMs: null,
        };
      }

      const startedAt = Date.now();

      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        const response = await fetch(service.baseUrl, {
          method: "HEAD",
          signal: controller.signal,
          cache: "no-store",
        });

        clearTimeout(timeout);

        return {
          key: service.key,
          label: service.label,
          url: env.NEXT_PUBLIC_SHOW_HEALTH_URLS ? service.baseUrl : undefined,
          status: response.ok ? ("reachable" as const) : ("unreachable" as const),
          latencyMs: Date.now() - startedAt,
        };
      } catch {
        return {
          key: service.key,
          label: service.label,
          url: env.NEXT_PUBLIC_SHOW_HEALTH_URLS ? service.baseUrl : undefined,
          status: "unreachable" as const,
          latencyMs: Date.now() - startedAt,
        };
      }
    })
  );

  return NextResponse.json({
    checkedAt: new Date().toISOString(),
    services: results,
  });
}
