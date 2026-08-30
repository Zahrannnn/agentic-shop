export const routes = {
  shop: "/shop",
  catalog: "/shop",
  login: "/auth/login",
  health: "/health",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];
