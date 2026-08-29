export const routes = {
  welcome: "/",
  login: "/auth/login",
  dashboard: "/dashboard",
  profile: "/profile",
  health: "/health",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];
