import { demoSession, sessionStorageKey } from "../constants/session";
import type { LoginInput, Session } from "../types";

export async function loginWithMockSession(input: LoginInput) {
  const session: Session = {
    user: {
      ...demoSession.user,
      email: input.email,
    },
  };

  window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
  return session;
}

export function readMockSession() {
  const rawSession = window.localStorage.getItem(sessionStorageKey);

  if (!rawSession) {
    return null;
  }

  try {
    return JSON.parse(rawSession) as Session;
  } catch {
    window.localStorage.removeItem(sessionStorageKey);
    return null;
  }
}

export function clearMockSession() {
  window.localStorage.removeItem(sessionStorageKey);
}
