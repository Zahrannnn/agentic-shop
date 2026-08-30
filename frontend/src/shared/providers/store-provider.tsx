"use client";

import { useEffect } from "react";
import { Provider } from "react-redux";
import type { ReactNode } from "react";
import { hydrateSession } from "@/features/shopping/store/session-slice";
import { store } from "@/shared/store/store";

export function StoreProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    store.dispatch(hydrateSession());
  }, []);

  return <Provider store={store}>{children}</Provider>;
}
