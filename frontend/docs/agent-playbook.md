# Agent Playbook

This playbook is the short path for agent-assisted changes. Use it with
`AGENTS.md`, `docs/architecture.md`, and `docs/development.md`.

## First Checks

- Read the current feature README before editing a feature.
- Check `src/features` before creating shared code.
- For Next.js routing, metadata, caching, route handlers, config, or build
  behavior, read the matching guide in `node_modules/next/dist/docs/`.

## Adding A Feature

- Prefer `npm run corelia -- feature <name>`.
- Keep the generated skeleton until real files replace `.gitkeep`.
- Export only intentional public APIs from `src/features/<feature>/index.ts`.
- Keep route files thin; route files should compose metadata, layouts, and
  feature exports.

## Feature Boundaries

- Put endpoint functions and adapters in `features/<feature>/api`.
- Put TanStack Query hooks and orchestration in `features/<feature>/hooks`.
- Put presentational UI in `features/<feature>/components`.
- Put Zod schemas and boundary validation in `features/<feature>/validations`.
- Use `src/shared` only for cross-feature infrastructure or truly generic
  primitives.

## Common Tasks

- New page: create a thin route in `src/app`, export the page UI from the
  owning feature barrel, and import from `@/features/<feature>`.
- REST call: use Axios through `src/shared/api/http-client.ts`, then wrap the
  call in a feature hook.
- Server state: use TanStack Query in feature hooks, not inside presentational
  components.
- Form: use TanStack Form with a Zod schema owned by the feature.
- Durable client state: use Redux Toolkit only for state that must survive
  across app areas.

## Verification

Run the smallest relevant check while working, then run the full handoff check
before claiming the change is complete:

```powershell
npm run verify
```

If Docker, CI, or deployment files changed, explain whether Docker validation
was run.
