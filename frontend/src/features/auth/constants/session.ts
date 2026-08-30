import type { Session } from "../types";

export const sessionStorageKey = "agentic-shop.auth.session";

export const demoSession: Session = {
  user: {
    id: "demo-user",
    name: "Frontend Lead",
    email: "you@example.com",
  },
};
