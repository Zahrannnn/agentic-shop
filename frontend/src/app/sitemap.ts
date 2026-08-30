import type { MetadataRoute } from "next";
import { env } from "@/shared/config/env";
import { routes } from "@/shared/constants/routes";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    routes.shop,
    routes.login,
    routes.health,
  ].map((route) => ({
    url: `${env.NEXT_PUBLIC_APP_URL}${route}`,
    lastModified: new Date(),
  }));
}
