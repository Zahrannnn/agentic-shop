# Development

## Local Setup

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Use `npm run verify` as the full local handoff check before considering an
implementation complete.

## Feature CLI

Interactive:

```powershell
npm run corelia -- feature
```

Non-interactive:

```powershell
npm run corelia -- feature customer-accounts
```

The CLI refuses existing feature names and generates the full feature skeleton.

## Environment

The root `.env.example` is the canonical contract. Backend services use explicit names:

```env
NEXT_PUBLIC_CORE_API_BASE_URL=
NEXT_PUBLIC_BILLING_API_BASE_URL=
NEXT_PUBLIC_REPORTING_API_BASE_URL=
```

`NEXT_PUBLIC_SHOW_HEALTH_URLS=true` allows the public `/health` page to display full backend URLs.

## Git Hooks

Husky runs a pre-commit hook with lint-staged and full lint. There is no Prettier requirement in this boilerplate.

## Docker

Root Dockerfile builds Next standalone output. A root `Makefile` wraps the
compose workflow; `infra/env.sh` is the container entrypoint and regenerates
`public/runtime-env.js` from the container env on every start, so changing
`infra/.env` and running `make up` (or `make restart`) applies new
`NEXT_PUBLIC_*` values without rebuilding. Ports are configurable from
`infra/.env`: `PORT` (public host port) and `APP_PORT` (app internal port,
default `3000`); Nginx upstream is rendered from `default.conf.template` via
the official image's envsubst.

```powershell
make env       # create infra/.env from example (first time)
make build     # build the image once
make up        # start; regenerates runtime env, no rebuild
make logs      # tail logs
make help      # list all targets
```

Known constraint: Next 16 declares Node `>=20.9.0`; the Dockerfile and CI use `node:22-alpine`.

## Testing

Vitest and Testing Library are installed for projects that want local tests.
Playwright is the recommended E2E path when a project is ready for browser
coverage, but it is not installed in the base.

```powershell
npm run test       # watch mode
npm run test:run   # single run
npm run verify     # lint, typecheck, tests, build
```

Agents should also read `docs/agent-playbook.md` for the short task map before
making larger changes.
