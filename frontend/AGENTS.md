<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# CORELIA Boilerplate Agent Workflow

## Before Editing

- Read `README.md`, `docs/architecture.md`, `docs/development.md`, and `docs/agent-playbook.md`.
- Read the relevant local Next docs in `node_modules/next/dist/docs/` before changing routing, metadata, caching, route handlers, config, or build behavior.
- Check existing feature ownership before creating shared code.
- Treat this repo as feature-first: `src/features/<feature>` owns its UI, hooks, API boundaries, constants, validations, utilities, and types.

## Implementation Rules

- Keep route files thin. Routes compose metadata, layouts, and feature exports.
- Cross-feature imports should go through each feature `index.ts`.
- Put shadcn primitives in `src/components/ui`.
- Put cross-feature infrastructure in `src/shared`.
- Components inside `features/*/components` should be presentational unless they are the feature shell.
- Use Axios for REST transport and TanStack Query for server state.
- Use TanStack Form and Zod for forms.
- Use Redux Toolkit only for durable client app state.
- Prefer Next metadata APIs for SEO. React Helmet is available only for client-only edge cases.
- Keep WCAG 2.2 AA basics in mind: labels, focus visibility, keyboard access, semantic regions, contrast, and reduced motion.

## Feature Creation

- Prefer the CLI: `npm run corelia -- feature <name>`.
- The CLI must refuse existing feature names.
- Generated feature folders should keep the full skeleton until real files replace `.gitkeep`.
- Export only intentional public APIs from `index.ts`.

## Verification

- Run `npm run verify` before claiming implementation is complete.
- Run `npm run lint` when lint-sensitive files change.
- If Docker or CI files change, explain whether Docker validation was run.
- Docker base is `node:22-alpine`, meeting Next 16's `>=20.9.0` Node requirement. `infra/.env.example` and the root `.env.example` are the deployment env contract.
