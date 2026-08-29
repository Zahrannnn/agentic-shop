import type { GuideItem } from "../types";

export const quickStart: GuideItem[] = [
  {
    title: "Install from lockfile",
    description: "Use npm install first. The lockfile keeps projects reproducible.",
  },
  {
    title: "Run the app",
    description: "Start with npm run dev and open the local Next app.",
  },
  {
    title: "Create a feature",
    description: "Use npm run corelia -- feature <name> and export through index.ts.",
  },
];

export const architectureRules: GuideItem[] = [
  {
    title: "Routes stay thin",
    description: "Route files compose feature modules and metadata.",
  },
  {
    title: "Features own behavior",
    description: "Types, API calls, hooks, constants, UI, and validation live together.",
  },
  {
    title: "Shared is strict",
    description: "Only cross-feature infrastructure and primitives belong in shared.",
  },
];

export const agentReadyUpdates: GuideItem[] = [
  {
    title: "One handoff command",
    description: "npm run verify now runs lint, typecheck, Vitest, and the production build.",
  },
  {
    title: "Agent playbook",
    description: "docs/agent-playbook.md maps common tasks to the right folders and checks.",
  },
  {
    title: "Copyable imports",
    description: "Starter routes import feature pieces from barrels instead of deep component paths.",
  },
];
