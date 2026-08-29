import type { ReactNode } from "react";

export type WelcomePageProps = {
  cachedDemo: ReactNode;
  dynamicDemo: ReactNode;
};

export type GuideItem = {
  title: string;
  description: string;
};
