# agentic-shop — frontend

The storefront for the agentic shopping system: a transcript where a shopping agent
streams answers and **generated UI plans** (result grids, comparisons, preference
chips, cart views) that this app renders. Plans are data documents validated with
Zod — the app never executes agent output.

Read [`../FRONTEND_GUIDE.md`](../FRONTEND_GUIDE.md) for the backend contract and
[`../DESIGN.md`](../DESIGN.md) for the design system ("The Curator's Desk").

## Stack

- **Next.js 16** (App Router, Cache Components, typed routes, React Compiler) +
  **React 19** + **TypeScript 5**
- **Tailwind CSS v4** with shadcn-style primitives in `src/components/ui`
- **Redux Toolkit** for the turn/session state, **TanStack Query** for server
  probes, **Axios** for plain REST, native **fetch + ReadableStream** for SSE turns
- **Zod 4** mirrors the backend UI-plan DSL (single source of truth:
  `../backend/fixtures/ui-plans/`)
- **Vitest** + **Testing Library**; **npm** as the package manager

## Quick start

```bash
# backend first (see ../backend/README.md): uvicorn on http://127.0.0.1:8000
npm install
npm run dev        # http://localhost:3000/shop
```

`NEXT_PUBLIC_AGENT_API_BASE_URL` overrides the backend address (default
`http://127.0.0.1:8000`; CORS is pre-allowed for the Next dev ports).

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | dev server |
| `npm run verify` | eslint + typecheck + vitest + production build (the handoff gate) |
| `npm run test:run` | vitest single run |
| `npm run lint` / `typecheck` / `build` | individually |

## Routes

- `/shop` — the storefront: transcript, thinking skeletons, plan renderer,
  contextual quick replies, catalog sheet (public, no auth)
- `/` welcome, `/dashboard`, `/profile`, `/auth/login` — boilerplate starters
- `/health` + `/api/health` — backend-mode views from the boilerplate

## The shopping feature (`src/features/shopping/`)

| Folder | Contents |
|---|---|
| `api/` | `agent-client.ts` (SSE POST transport), `sse-frame-parser.ts` (chunk-safe frame extractor), `catalog-client.ts` (browse feed) |
| `hooks/` | `use-agent-turn` — drives one turn: request → parser → store actions |
| `store/` | RTK slices: `session` (identity + sessionStorage), `transcript` (turns, phases, plans) |
| `validations/` | Zod mirror of the UI-plan DSL + `parseUiPlan` gate |
| `components/` | plan renderer registry (6 components), transcript UI, thinking skeletons, quick replies, catalog sheet |
| `utils/` | catalog id mirror (contract-checked against the backend dataset) |

## Contract tests

`validations/plan-schema.test.ts` loads the five backend fixtures from
`../backend/fixtures/ui-plans/` and must accept all of them while rejecting
known-bad mutations. If the backend catalog changes, regenerate
`utils/catalog-refs.ts` — the test suite fails loudly until the mirror matches.

## House rules

See `AGENTS.md` and `docs/` (feature-first layout, thin routes, Next 16 caveats).
Design doctrine: `../DESIGN.md` — light "Curator's Desk" palette, one teal-ink
accent, no AI-slop patterns.
