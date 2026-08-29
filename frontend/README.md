# CORELIA Next Boilerplate

Feature-first frontend boilerplate for CORELIA product applications. Built for
authenticated SaaS-style apps, external REST backends, Docker/Nginx deployment,
GitLab CI, and agent-friendly development.

## Stack

- **Next.js 16** (App Router, Cache Components, typed routes, React Compiler,
  standalone output, Turbopack filesystem cache for builds)
- **React 19**, **TypeScript 5** (strict)
- **Tailwind CSS v4** with shadcn-style primitives in `src/components/ui`
- **Axios** for REST transport
- **TanStack Query** for server state, **TanStack Form** for form state,
  **TanStack Table** for data tables, **TanStack Pacer** for rate-limited input
- **Zod 4** for boundary validation (env, forms, risky API guards)
- **Redux Toolkit** for durable client app state only
- **next-themes**, **sonner**, **react-helmet-async**, **lucide-react**
- **Vitest** + **Testing Library** for unit/component tests (configured, with
  example tests). Playwright is the recommended E2E path when a project is ready.

## Quick start

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Scripts

Script surface is intentionally minimal. `npm run verify` is the preferred
handoff check for agents and contributors.

```powershell
npm run dev        # start dev server
npm run build      # production build
npm run start      # serve built output
npm run lint       # eslint
npm run typecheck  # TypeScript without emit
npm run test       # Vitest watch mode
npm run test:run   # Vitest single run
npm run verify     # lint, typecheck, tests, build
npm run corelia -- feature <name>   # scaffold a feature module
```

## Routes

- `/` developer welcome page and Cache Components demo
- `/auth/login` mock provider-agnostic login
- `/dashboard` protected dashboard starter
- `/profile` protected TanStack Form starter
- `/health` public backend health view
- `/api/health` route handler proxying configured backend services

Route groups: `src/app/(app)` protected shell, `src/app/(auth)` auth flows,
`src/app/(public)` public pages.

## Architecture

```text
src/
  app/              # Next route tree, layouts, providers, metadata
  components/ui/    # shadcn-style primitives
  features/         # product/domain feature modules
  shared/           # cross-feature infrastructure and primitives
```

Feature module skeleton (every feature owns all of these):

```text
src/features/<feature>/
  README.md
  types.ts
  index.ts
  api/          # endpoint functions and adapters
  components/   # presentational UI
  constants/
  hooks/        # TanStack Query hooks and orchestration
  utils/
  validations/  # Zod schemas and boundary guards
```

Read `docs/architecture.md` and `docs/development.md` before adding new app
areas. Agents should also read `AGENTS.md` and `docs/agent-playbook.md`.

### Data and state

- Axios handles REST transport. `src/shared/api/http-client.ts` provides cached
  per-service clients (`core`, `billing`, `reporting`) and a normalized
  `ApiError` shape.
- TanStack Query owns server state.
- TanStack Form + Zod own form state and validation.
- Redux Toolkit is available for durable client app state only
  (`src/shared/store`). Prefer React local state for one-screen UI state.
- Prefer Next metadata APIs for SEO. React Helmet is for client-only edge cases.

### Mutations

Mutations are wrapped in feature hooks (`features/*/hooks`), never called raw
inside presentational components. A feature mutation hook standardizes the
`useMutation` call, toast feedback, and cache invalidation. See
`src/features/profile/hooks/use-save-profile.ts` for the canonical pattern.

### Validation

Zod is used consistently at boundaries:

- `src/shared/config/env.ts` validates public env at import time.
- `features/*/validations` holds form schemas (e.g. `profile-schema.ts`).
- Optional Zod guards at risky API boundaries. Internal objects are not
  validated; only the risky edges.

### API typing

Manual TypeScript types are the baseline. Add optional Zod guards at risky
boundaries where backend contracts are unreliable. Generated OpenAPI clients are
not required by the base; add per project when the backend contract is reliable.

### File uploads and downloads

`src/shared/api/file-transfer.ts` provides shared helpers:

- `downloadBlob(client, url, fallbackFileName?)` — blob download with
  content-disposition filename parsing.
- `uploadFile(client, url, file, fieldName?, onProgress?)` — multipart upload
  with progress callbacks.
- `getFileNameFromDisposition(disposition?)` — parses quoted, unquoted, and
  `filename*=UTF-8''` forms.

These are shared utilities, not a feature. Compose them inside feature hooks.

### Responsive behavior

Desktop-first product shell with solid mobile support. The sidebar collapses to
a sheet on small screens, forms stay usable on phones, and tables use overflow
or card alternatives where needed.

## Environment

The root `.env.example` is the canonical contract. `infra/.env.example` mirrors
the deployment contract.

```env
NEXT_PUBLIC_APP_NAME=CORELIA Next Boilerplate
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_SHOW_HEALTH_URLS=true
NEXT_PUBLIC_CORE_API_BASE_URL=
NEXT_PUBLIC_BILLING_API_BASE_URL=
NEXT_PUBLIC_REPORTING_API_BASE_URL=
```

`NEXT_PUBLIC_SHOW_HEALTH_URLS=true` lets the public `/health` page display full
backend URLs. Env is validated with Zod at import time, so missing or malformed
values fail fast in dev.

## Feature CLI

```powershell
npm run corelia -- feature customer-accounts   # non-interactive
npm run corelia -- feature                     # interactive prompt
```

The CLI refuses existing feature names and generates the full feature skeleton
with `.gitkeep` placeholders. Replace placeholders as folders gain real files.

## Testing

Vitest, Testing Library, and jsdom are installed and configured
(`vitest.config.ts`, `vitest.setup.ts`). An example test lives at
`src/shared/api/file-transfer.test.ts`. Run tests with:

```powershell
npm run test
npm run test:run
```

Run the full handoff check with:

```powershell
npm run verify
```

Playwright is the recommended E2E path when a project is ready for browser
coverage; install and configure it per project.

## Git hooks

Husky runs a pre-commit hook with lint-staged and full lint. There is no
Prettier requirement in this boilerplate.

## Deployment

Default path: Docker standalone output behind Nginx, built via GitLab CI.

```powershell
make env       # create infra/.env from example (first time)
make build     # build the image once
make up        # start; regenerates runtime env, no rebuild
```

Local Nginx smoke test (no Make): `cd infra && cp .env.example .env && docker compose up --build`.

The root `Dockerfile` builds Next standalone output. `infra/docker-compose.yml`
runs the app behind Nginx. Ports are configurable from `infra/.env`:
`PORT` is the public host port Nginx listens on; `APP_PORT` (default `3000`) is
the app's internal port. `infra/env.sh` is the container entrypoint: on every
start it writes `public/runtime-env.js` from the container environment, so
`NEXT_PUBLIC_*` changes take effect on `make up` / `make restart` without
rebuilding. `.gitlab-ci.yml` has `build_app` and `build_image` stages; images
push to `$HUB_URL/$APP_NAME:$APP_VERSION` on the default branch or tags.

Make targets: `help`, `env`, `build`, `up`, `rebuild`, `down`, `restart`,
`logs`, `ps`, `shell`, `push`, `clean`.

## Known constraint

Next 16 declares Node `>=20.9.0`. The Docker base is `node:22-alpine`, which
meets that requirement. `NEXT_PUBLIC_*` values are substituted at container
start via `infra/env.sh` (writing `public/runtime-env.js`), so env changes do
not require a rebuild; server-side env is read from `process.env` at runtime.

## Documentation

- `docs/agent-playbook.md` - short task map for agent-assisted changes.

- `docs/architecture.md` — top-level layout, feature modules, shared code, data
  and state, Next 16 patterns.
- `docs/development.md` — local setup, feature CLI, env, git hooks, Docker,
  testing.
- `AGENTS.md` — agent workflow rules for editing this repo safely.
