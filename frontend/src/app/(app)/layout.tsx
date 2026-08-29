import type { ReactNode } from "react";
import { AuthGate } from "@/features/auth";
import { AppShell } from "@/shared/components/layout/app-shell";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
