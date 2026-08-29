# Architecture

## Top-Level Layout

```text
src/
  app/              # Next route tree, layouts, providers, metadata
  components/ui/    # shadcn-style primitives
  features/         # product/domain feature modules
  shared/           # cross-feature infrastructure and primitives
```

## Feature Modules

Every starter feature uses the full skeleton:

```text
src/features/<feature>/
  README.md
  types.ts
  index.ts
  api/
  components/
  constants/
  hooks/
  utils/
  validations/
```

Feature rules:

- Export public APIs through `index.ts`.
- Keep feature-local types in `types.ts`.
- Put endpoint functions and adapters in `api/`.
- Put TanStack Query hooks and stateful orchestration in `hooks/`.
- Put presentational UI in `components/`.
- Put Zod schemas and boundary validation in `validations/`.

## Shared Code

Use `src/shared` only for cross-feature infrastructure:

- API client foundation
- providers
- app shell and feedback components
- route constants
- env validation
- Redux store
- generic utilities

Do not move feature-specific tables, schemas, cards, hooks, or endpoint functions into shared just because a second feature might someday need them.

## Data And State

- Axios handles REST transport.
- TanStack Query owns server state.
- TanStack Form and Zod own form state and validation.
- Redux Toolkit is available for durable client app state.
- React local state is still preferred for one-screen UI state.

## Next 16 Patterns

This boilerplate enables:

- `typedRoutes`
- `reactCompiler`
- `cacheComponents`
- standalone output
- Turbopack filesystem cache for builds

Read local Next docs before changing these settings.
