"use client";

import { useDebouncedCallback } from "@tanstack/react-pacer";

export function useRateLimitedSearch(onSearch: (value: string) => void) {
  return useDebouncedCallback(onSearch, {
    wait: 250,
  });
}
