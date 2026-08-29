"use client";

import { HelmetProvider as ReactHelmetProvider } from "react-helmet-async";
import type { ReactNode } from "react";

export function HelmetProvider({ children }: { children: ReactNode }) {
  return <ReactHelmetProvider>{children}</ReactHelmetProvider>;
}
