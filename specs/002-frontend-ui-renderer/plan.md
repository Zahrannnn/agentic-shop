# Implementation Plan: Frontend UI Renderer & Chat (Phase 2)

**Branch**: `002-frontend-ui-renderer` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-frontend-ui-renderer/spec.md`

**Note**: This template is filled in by the `$speckit-plan` command; its definition describes the execution workflow.

## Summary

Build the Phase 2 frontend on the owner-supplied CORELIA Next.js boilerplate at
`frontend/`: a public shopping page that hosts the chat transcript, streams agent turns
over the frozen POST + SSE contract via native `fetch` + `ReadableStream` with a
chunk-split-tolerant frame parser, and renders every `ui_update` through a fixed
registry of six plan components behind a Zod v4 validation gate that mirrors the
backend DSL. Redux Toolkit holds the durable turn/session state; the interactive loop
(wire plan actions and free text back, manage session id + resume/404/409 lifecycle)
reuses the same turn pipeline. The Zod schemas are proven against the backend's five
fixture JSONs (read from `backend/fixtures/ui-plans/`) — the D8 double-sided contract —
inside the boilerplate's existing vitest suite, gated by `npm run verify`.

## Technical Context

**Language/Version**: TypeScript 5 (strict) on Next.js 16.2.10 (App Router,
`typedRoutes`, `reactCompiler`, `cacheComponents`) + React 19.2; Node per
`frontend/.nvmrc` (22; Next 16 requires >= 20.9)

**Primary Dependencies**: Already in the boilerplate (`frontend/package.json`): Zod 4
(boundary validation), Redux Toolkit 2 + react-redux 9 (durable client state),
TanStack Query 5 (server state — reused for `/health` mode badge), Axios 1 (REST via
`src/shared/api/http-client.ts`; NOT used for the SSE turn stream), Tailwind v4 +
shadcn-style primitives in `src/components/ui`, Vitest 4 + Testing Library +
jsdom. No new runtime dependencies are added.

**Storage**: None — conversation state lives in the Redux store (client-side, per
browser tab); session state remains server-side in the backend's memory exactly as in
Phase 1. A backend restart expires sessions by design; the client recovers via the
resume → 404 → fresh-session flow (FR-010).

**Testing**: Vitest + Testing Library (jsdom) — three layers: (a) pure unit tests
(frame parser, session id rules, reducer transitions); (b) contract tests reading
`backend/fixtures/ui-plans/*.json` from disk through the Zod mirror (accept all five,
reject known-bad mutations); (c) component tests with a mock `fetch` returning a
chunked `ReadableStream` to drive the real turn pipeline end-to-end at the component
level. No E2E framework in MVP (Playwright is pre-recommended by the boilerplate but
not installed — deferred).

**Target Platform**: Modern evergreen browsers, served by `next dev` /
`next start` / the boilerplate's Docker standalone output; developer machines
(Windows/macOS/Linux) and CI-friendly — unit/contract tests require no backend and no
credentials (mock-mode backend only for the joint smoke run)

**Project Type**: web app (Next.js feature-first boilerplate; new code concentrated in
one feature module `src/features/shopping/` plus a thin public route and two small
shared/ extensions)

**Performance Goals**: Mock-mode turn fully rendered (send → terminal frame → plan
visible) well under 2 s of client overhead over the backend's < 5 s turn; frame
parsing and reducer updates batched so streaming text appends without frame drops;
`npm run verify` completes as a normal boilerplate handoff check

**Constraints**: The backend contract is frozen (`specs/001-backend-agent-scaffold/
contracts/http-api.md`, `contracts/ui-dsl.md` + fixture corpus) — the client adapts,
never the contract; no
plan patching (full replace per D2); plans are data — no `eval`, no HTML injection
from plan strings; no new runtime deps (principle VIII); no auth on the shop route;
base URL from validated public env only; Next.js 16 has breaking changes vs. training
data — read `node_modules/next/dist/docs/` before touching routing/metadata/config
(`frontend/AGENTS.md` rule)

**Scale/Scope**: One feature module (~6 registry components, 1 turn pipeline, 2 Redux
slices, 1 route), 5 user stories, single-user local deployment, MVP scope of the
frozen 6-component registry — no V2 items (patching, extra components, persistence)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Compliance | Status |
|---|-----------|------------|--------|
| I | Decisions Record Is Binding | D1 (transcript), D2 (full replace — no patching code anywhere), D7 (exact event vocabulary and lock/unlock contract), D8 core (Zod mirror + fixtures, Tailwind + shadcn) implemented verbatim. Two recorded deviations, both "owner-supplied boilerplate wins" (D8 open item 1 anticipated adapting to the boilerplate): client state **Redux Toolkit** instead of zustand, package manager **npm** instead of pnpm — both are the boilerplate's own shipped standards (`src/shared/store/store.ts`, `package-lock.json` + `"packageManager": "npm@10.2.5"`); owner adjudicated both at Phase 2 kick-off. Rationale recorded in research.md R2/R3. | ✅ PASS (2 recorded deviations, owner-adjudicated) |
| II | LLM Access Behind the Factory | Backend principle — untouched. The frontend talks only to the frozen HTTP/SSE surface and never sees a model, key, or gateway; base URL comes from validated public env (`src/shared/config/env.ts` pattern). No key material anywhere in frontend code or tests. | ✅ PASS |
| III | Deterministic Core, Narrative Edge | Backend principle — preserved by consumption: mock mode is the dev/CI mode; rankings arrive precomputed and are rendered in order; the client adds no ordering, randomness, or time-dependent logic (session id uses `crypto.randomUUID`, which is identity, not behavior). | ✅ PASS |
| IV | Structured Outputs or No Outputs | Mirrored client-side as principle V's gate: every plan passes the Zod schema before render; failure renders the plan-region error state, never partial content, never a silent fallback (FR-006). | ✅ PASS |
| V | Contract-First UI DSL | Zod v4 mirror of `contracts/ui-dsl.md` lives in `features/shopping/validations/`; contract tests read `backend/fixtures/ui-plans/*.json` (single source of truth) and must accept all five + reject known-bad mutations (unknown type, foreign productId, out-of-bounds arrays, disallowed action). Unknown plan types are rejected, never forward-compatibly rendered. | ✅ PASS |
| VI | Phase Discipline | Phase 2 is owner-declared (branch `002-frontend-ui-renderer`; AGENTS.md phase note superseded by the owner's instruction to build the frontend). Scope stays inside `frontend/` and `specs/002-frontend-ui-renderer/`; no edits to `PRD.md`/`DECISIONS.md`; backend code untouched except *reading* its fixture files. | ✅ PASS (unlocked by owner for this phase) |
| VII | Quality Gates Before Any PR | Frontend equivalent of the gates: `npm run verify` (lint → typecheck → test → build) from `frontend/`, per the boilerplate's own handoff rule; backend gates (`uv run ruff`/`pytest`) re-run to prove the shared fixtures still pass on their side. Both gate sets run in quickstart.md and tasks.md. | ✅ PASS |
| VIII | Simplicity and Deferred Complexity | Exactly the frozen 6-component registry; no plan patching (V2 backlog); no new runtime dependencies; no E2E framework install in MVP; no shared/ sprawl (only env var + store registration, both cross-feature by definition); no optimistic UI, no retry storms — one turn in flight, server owns ordering. | ✅ PASS |

**Post-design re-check**: the Zod schema set (data-model.md) maps 1:1 onto
`contracts/ui-dsl.md`; the RTK slices hold only client-durable turn/session state
(no server-state duplication — `/health` stays in TanStack Query); the frame parser
is a pure function with no framework coupling. No V2 capability (patching, extra
components, persistence, auth) leaked into the design.

## Project Structure

### Documentation (this feature)

```text
specs/002-frontend-ui-renderer/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── checklists/
│   └── requirements.md  # Spec quality checklist ($speckit-specify output)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

(The Phase 1 pack additionally shipped `contracts/`; this phase consumes the frozen
Phase 1 contracts and adds no new wire contract, so no contracts/ folder is created.)

### Source Code (repository root)

```text
frontend/
├── .env.example                       # extended: NEXT_PUBLIC_AGENT_API_BASE_URL
├── src/
│   ├── app/
│   │   └── (public)/
│   │       └── shop/
│   │           └── page.tsx           # thin public route: metadata + <ShoppingPage/>
│   ├── shared/
│   │   ├── config/env.ts              # + NEXT_PUBLIC_AGENT_API_BASE_URL (validated)
│   │   ├── constants/routes.ts        # + shop: "/shop"
│   │   └── store/store.ts             # register agent slices (session, transcript)
│   ├── features/
│   │   └── shopping/
│   │       ├── README.md              # feature ownership doc (house style)
│   │       ├── index.ts               # public barrel: ShoppingPage + hook exports
│   │       ├── types.ts               # feature-level TS types (Turn, SessionView…)
│   │       ├── api/
│   │       │   ├── agent-client.ts        # POST /api/chat via fetch; health fetch
│   │       │   ├── sse-frame-parser.ts    # pure accumulate → split frames parser
│   │       │   └── sse-frame-parser.test.ts
│   │       ├── validations/
│   │       │   ├── ui-plan-schema.ts      # Zod v4 mirror of contracts/ui-dsl.md
│   │       │   ├── ui-plan-schema.test.ts # fixture contract tests (5 pass / bad fail)
│   │       │   └── fixtures.ts            # fs loader for backend/fixtures/ui-plans/
│   │       ├── store/                     # feature-owned RTK slices
│   │       │   ├── session-slice.ts       # sessionId, live flag
│   │       │   ├── transcript-slice.ts    # turns: status/deltas/plan/terminal
│   │       │   └── transcript-slice.test.ts
│   │       ├── hooks/
│   │       │   ├── use-agent-turn.ts      # send/abort + stream → dispatch pipeline
│   │       │   ├── use-health-badge.ts    # TanStack Query over /health
│   │       │   └── use-agent-turn.test.tsx
│   │       ├── components/
│   │       │   ├── ShoppingPage.tsx       # feature shell: transcript + composer
│   │       │   ├── TranscriptView.tsx     # turn list (user bubbles + agent turns)
│   │       │   ├── StatusStepper.tsx      # lifecycle stages indicator
│   │       │   ├── MessageComposer.tsx    # locked-while-streaming input
│   │       │   ├── PlanRegion.tsx         # validation gate + registry switch
│   │       │   ├── registry.ts            # plan type → component map (fixed)
│   │       │   ├── ProductGridCard.tsx        # product_grid
│   │       │   ├── PreferencePicker.tsx       # preference_picker
│   │       │   ├── ComparisonTable.tsx        # comparison_table
│   │       │   ├── ProductDetails.tsx         # product_details
│   │       │   ├── CartView.tsx               # cart_view
│   │       │   ├── TextBlock.tsx              # text_block
│   │       │   └── PlanErrorState.tsx     # invalid-plan / empty-state fallback UI
│   │       ├── constants/
│   │       │   └── lifecycle.ts           # stage order, bounds, allowed-action tables
│   │       └── utils/
│   │           └── catalog-refs.ts        # known product-id set for mirror validation
│   └── components/ui/                     # existing shadcn primitives (consumed only)
└── vitest.config.ts                       # existing; no changes expected

backend/                                    # UNCHANGED — fixtures read-only input
└── fixtures/ui-plans/*.json               # single source of truth for contract tests
```

**Structure Decision**: One feature module under the boilerplate's feature-first
layout, exactly per `frontend/docs/architecture.md` rules: validations (Zod) in
`features/shopping/validations`, orchestration hooks in `hooks/`, presentational
components in `components/`, the SSE transport in `api/`, RTK slices in the feature's
own `store/` (registered in `shared/store/store.ts`, which is the cross-feature
composition point). The route lives in `src/app/(public)/shop/` because `(public)` is
the only route group without the `AuthGate` wrapper (verified in
`src/app/(app)/layout.tsx`) and the shop must be reachable without authentication.
Shared/ receives only two additions the boilerplate itself defines as shared concerns:
the env var (`src/shared/config/env.ts`) and the store registration.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty. The two D8 deviations (RTK, npm) are
recorded and justified under principle I in the Constitution Check and in
research.md R2/R3; they are boilerplate-conformant choices, not added complexity.
