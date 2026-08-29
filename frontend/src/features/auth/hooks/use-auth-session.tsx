"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  clearMockSession,
  loginWithMockSession,
  readMockSession,
} from "../api/session-adapter";
import type { LoginInput, Session } from "../types";
import { routes } from "@/shared/constants/routes";

type AuthContextValue = {
  session: Session | null;
  user: Session["user"] | null;
  loading: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setSession(readMockSession());
      setLoading(false);
    }, 0);

    return () => window.clearTimeout(timeout);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      loading,
      login: async (input) => {
        const nextSession = await loginWithMockSession(input);
        setSession(nextSession);
        router.push(routes.dashboard);
      },
      logout: () => {
        clearMockSession();
        setSession(null);
        router.push(routes.login);
      },
    }),
    [loading, router, session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return value;
}
