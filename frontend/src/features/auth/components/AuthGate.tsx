"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { routes } from "@/shared/constants/routes";
import { useAuth } from "../hooks/use-auth-session";

export function AuthGate({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !session) {
      router.replace(`${routes.login}?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, pathname, router, session]);

  if (loading || !session) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <Skeleton className="h-32 w-full max-w-md" />
      </main>
    );
  }

  return children;
}
