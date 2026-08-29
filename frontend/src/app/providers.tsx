"use client";

import type { ReactNode } from "react";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/features/auth";
import { HelmetProvider } from "@/shared/providers/helmet-provider";
import { AppQueryProvider } from "@/shared/providers/query-provider";
import { StoreProvider } from "@/shared/providers/store-provider";
import { ThemeProvider } from "@/shared/providers/theme-provider";
import { WebVitals } from "@/shared/components/feedback/web-vitals";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <HelmetProvider>
      <StoreProvider>
        <AppQueryProvider>
          <ThemeProvider>
            <AuthProvider>
              {children}
              <WebVitals />
              <Toaster />
            </AuthProvider>
          </ThemeProvider>
        </AppQueryProvider>
      </StoreProvider>
    </HelmetProvider>
  );
}
