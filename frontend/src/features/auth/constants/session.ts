import type { Session } from "../types";

export const sessionStorageKey = "corelia.session";

export const demoSession: Session = {
  user: {
    id: "demo-user",
    name: "Frontend Lead",
    email: "lead@corelia.local",
  },
};
