# Research & Decisions — Frontend UI Renderer & Chat (Phase 2)

**Feature**: `002-frontend-ui-renderer` | **Date**: 2026-08-29

Phase 0 output. The wire-level behavior is already frozen by the Phase 1 contracts
(`specs/001-backend-agent-scaffold/contracts/http-api.md`, `contracts/ui-dsl.md`,
`FRONTEND_GUIDE.md`); this file records the *implementation-level* decisions needed to
build the client inside the owner-supplied boilerplate, each with rationale and
alternatives considered. Two decisions are recorded deviations from DECISIONS.md D8,
both adjudicated by the owner at Phase 2 kick-off ("owner-supplied boilerplate
conventions win" — the same principle D8's Open Item 1 anticipated). No NEEDS
CLARIFICATION items remain.

## R1 — Boilerplate inventory & adoption boundary

- **Decision**: Adopt the CORELIA boilerplate as-is and put all new code in one
  feature module `src/features/shopping/` plus a thin public route `src/app/(public)/
  shop/page.tsx` and two shared/ extensions (env var, store registration). Existing
  inventory kept unchanged: Next.js 16.2.10 app router with `typedRoutes`,
  `reactCompiler`, `cacheComponents`, standalone output (`frontend/next.config.ts`);
  React 19.2, TS 5 strict; Tailwind v4 + 16 shadcn primitives in `src/components/ui`
  (badge, button, card, checkbox, dialog, dropdown-menu, input, label, select,
  separator, sheet, skeleton, sonner, table, tabs, textarea); Axios + `ApiError`
  normalization (`src/shared/api/http-client.ts`); TanStack Query
  (`src/shared/providers/query-provider.tsx`); RTK store + `StoreProvider`
  (`src/shared/store/store.ts`, `src/shared/providers/store-provider.tsx`); env
  validation with runtime override hook (`src/shared/config/env.ts` reading
  `window.__RUNTIME_CONFIG__`); vitest + Testing Library + jsdom
  (`vitest.config.ts`, example test `src/shared/api/file-transfer.test.ts`); feature
  CLI `npm run corelia -- feature <name>`; handoff gate `npm run verify`.
- **Rationale**: `frontend/AGENTS.md`, `docs/architecture.md`, and
  `docs/agent-playbook.md` mandate exactly this feature-first placement (feature owns
  api/hooks/components/validations/constants/types/index; shared only for
  cross-feature infrastructure). The store and env are by definition cross-feature,
  so extending them is the sanctioned pattern; everything shopping-specific stays in
  the feature.
- **Alternatives considered**: building the feature as plain components under
  `src/app` (violates the boilerplate's feature-first rules); a separate package/
  workspace (violates the adjudicated monorepo-at-`frontend/` layout and adds tooling
  for no benefit at this scale).

## R2 — Package manager: npm, not pnpm (recorded D8 deviation)

- **Decision**: Use npm. No `pnpm-lock.yaml`/`pnpm-workspace.yaml` exists; the
  boilerplate ships `frontend/package-lock.json` and `"packageManager": "npm@10.2.5"`
  in `frontend/package.json`; all docs (`README.md`, `docs/development.md`) use npm
  commands; the feature CLI is `npm run corelia`.
- **Rationale**: DECISIONS.md D8 says "pnpm (frontend)" but also lists the frontend
  as "User's Next.js boilerplate (pending)" with adaptation as the open item; the
  owner adjudicated at Phase 2 kick-off that boilerplate conventions win. Fighting the
  shipped lockfile would mean regenerating it and diverging from every doc in the
  repo. This is a recorded deviation, to be folded into DECISIONS.md at the owner's
  next amendment (per constitution governance, this plan does not edit that file).
- **Alternatives considered**: pnpm import + lockfile regeneration (churn, breaks
  documented workflow, no functional gain); yarn (same objections, weaker toolchain
  fit with `packageManager` pinning).

## R3 — Client state: Redux Toolkit, not zustand (recorded D8 deviation)

- **Decision**: Durable client state (session identity + turn transcript) lives in
  Redux Toolkit slices owned by the feature (`features/shopping/store/session-slice.ts`,
  `transcript-slice.ts`) and registered in `src/shared/store/store.ts` next to the
  existing `preferencesSlice`. Everything else stays where the boilerplate puts it:
  server state (`/health` mode badge) in TanStack Query; one-screen ephemeral UI
  (composer draft text, local open/closed toggles) in React local state.
- **Rationale**: D8 says "zustand", but the boilerplate ships RTK 2 + react-redux 9
  with a configured provider and an exemplar slice (`src/shared/store/preferences-
  slice.ts`) — same owner-adjudicated "boilerplate wins" as R2. RTK also fits the
  shape of this state well: a normalized, externally-event-driven transcript
  (streaming events dispatched as actions) benefits from `createSlice` +
  `createAsyncThunk`-style explicit transitions and devtools time-travel while
  debugging stream races.
- **Alternatives considered**: zustand (adds a dependency against the grain of the
  boilerplate; principle VIII); keeping the transcript in TanStack Query (it is not
  server state — the server holds its own session state and the stream is POST-
  initiated, not cacheable/query-keyed); pure component state (the transcript must
  survive route transitions within the app and be inspectable across components —
  it is durable by the boilerplate's own definition).

## R4 — SSE transport: native fetch + ReadableStream; pure frame parser

- **Decision**: `features/shopping/api/agent-client.ts` POSTs `/api/chat` with
  `fetch` and consumes `response.body.getReader()` (TextDecoder over chunks),
  feeding a pure parser `api/sse-frame-parser.ts`: accumulate raw text; split
  complete frames on the `\n\n` separator while retaining the trailing partial
  buffer; each frame splits on its first `\n` into `event: ` and `data: ` lines;
  `JSON.parse` only the data payload; tolerate a final frame without the trailing
  blank line (flush on stream end); ignore frames with unparsable data lines as
  protocol violations. Non-200 responses are read as JSON error bodies (404
  `unknown_session`, 409 `turn_in_flight`, 422) and mapped to typed results before
  any streaming starts.
- **Rationale**: `FRONTEND_GUIDE.md` §4 and §9 (pitfall 7) mandate exactly this:
  `EventSource` cannot POST the request body, and Axios cannot stream a response in
  the browser (no incremental `response.body` access for `responseType: 'json'`
  patterns; it buffers). The frozen contract's frame shape is two lines + blank
  separator, so the accumulate-and-split parser is trivially testable as a pure
  function — hostile chunk splits (mid-frame, mid-separator) become unit-test
  inputs, which is the whole point of SC-002.
- **Alternatives considered**: `EventSource` (GET-only — cannot send the JSON body;
  rejected by the guide); Axios with `onDownloadProgress` (progress chunks are not
  guaranteed atomic or ordered for XHR-based adapters; non-standard for streaming);
  a Next.js route-handler proxy that re-emits the stream (extra hop and a second
  parser; CORS is already solved server-side via `ALLOWED_ORIGINS` defaults per
  `contracts/http-api.md` — keep the proxy as a documented deployment fallback
  only); a SSE client library (violates principle VIII for a 5-event vocabulary we
  must parse precisely anyway).

## R5 — Zod v4 mirror strategy + fs-based fixture loading (monorepo path assumption)

- **Decision**: `features/shopping/validations/ui-plan-schema.ts` mirrors
  `specs/001-backend-agent-scaffold/contracts/ui-dsl.md` in Zod v4 (already the
  boilerplate's pinned major, `zod@^4.4.3`): envelope (`planVersion === "1"`,
  non-empty `sessionId`, integer `turnId >= 1`), discriminated union on `root.type`
  over the six component prop shapes with exact bounds (grid 1–6 ids; picker 2–4
  options with a matching `select_preference` action per option; comparison 2–3 ids,
  ≤1 `choose`; details/cart/text with their fixed shapes), allowed-action sets per
  type, non-empty labels, and a catalog-membership refinement for every
  `productId`. The known catalog id set lives in `features/shopping/utils/
  catalog-refs.ts` and is cross-checked in tests against the backend's actual
  catalog (`backend/app/catalog/data/headphones.json`) read via `node:fs` — same
  mechanism as the fixtures. `validations/fixtures.ts` resolves the fixture
  directory as `../../../../backend/fixtures/ui-plans/` relative to the module
  (monorepo-root assumption: `frontend/` and `backend/` are siblings in the same
  checkout), reads the five JSONs at test time only (never shipped in the client
  bundle).
- **Rationale**: Principle V and D8 Open Item 4 make `backend/fixtures/ui-plans/` the
  single source of truth — duplicating fixture JSONs into the frontend would create a
  second truth that drifts. Reading them via fs in vitest (Node context, jsdom env
  still allows `node:fs` imports in test files) proves the *client's* schema accepts
  what the *backend* actually emits, which is the D8 double-sided obligation. The
  catalog cross-check keeps the foreign-productId rejection honest without
  hard-coding 28 ids twice without a drift alarm.
- **Alternatives considered**: hand-copied fixture files under `frontend/` (second
  source of truth — violates V); fetching fixtures from the backend at test time
  (network dependency in tests — forbidden by the Phase 1 precedent SC-006);
  a shared workspace package for schemas (monorepo tooling the boilerplate doesn't
  use; the contracts are frozen so mirror-drift risk is covered by the fixture
  tests themselves); runtime catalog fetch for validation (the renderer may *assume*
  valid product ids per FRONTEND_GUIDE §5; membership is a contract-test concern).

## R6 — Route placement: `/shop` under the `(public)` group (no auth)

- **Decision**: The shopping experience lives at `src/app/(public)/shop/page.tsx`
  (route `/shop`), added to `src/shared/constants/routes.ts`. The boilerplate's
  welcome home `/` stays untouched.
- **Rationale**: Verified in code — `src/app/(app)/layout.tsx` wraps every `(app)`
  page in `AuthGate` (`src/features/auth/components/AuthGate.tsx`), which redirects
  to `/auth/login` unless a mock session exists in `localStorage`
  (`src/features/auth/api/session-adapter.ts`). That directly violates the shop's
  no-authentication requirement. `(public)` (home, `/health`) has no gate, and the
  root `Providers` tree (`src/app/providers.tsx`) — Query, Store, Theme — wraps the
  whole app including `(public)`, so the feature needs no provider work. A dedicated
  `/shop` path also keeps the existing welcome page intact and gives the feature a
  stable, bookmarkable URL.
- **Alternatives considered**: replacing the welcome home at `(public)/page.tsx`
  (destroys the boilerplate's Cache Components demo and couples the feature to `/`);
  under `(app)` + auto-login (adds fake-auth coupling to a feature that must work
  signed-out; `AuthGate`'s redirect would still flash for anonymous users); a
  middleware-level auth exemption (fragile, fights the boilerplate's group
  convention).

## R7 — Renderer registry mapping to existing shadcn primitives

- **Decision**: `features/shopping/components/registry.ts` is a fixed `Record<PlanType,
  ComponentType>` switch over the six kinds; each component composes only primitives
  already present in `src/components/ui` (no new shadcn installs):
  - `product_grid` → **Card** (per product, grid layout), **Badge** (rank), **Button**
    (compare / details / add_to_cart per card)
  - `preference_picker` → **Card** (question), **Button** variant="outline" as chips
    (one per option, wired to its matching `select_preference` action)
  - `comparison_table` → **Table** (+ TableHeader/Body/Row/Cell), single **Button**
    CTA for `choose`
  - `product_details` → **Card**, **Separator** between spec groups, quotes as
    blockquote-styled list; **Badge** for attributes
  - `cart_view` → **Card** + **Table** (items, quantity, line total), **Button**
    (remove_from_cart), **Badge**/**CardTitle** for total
  - `text_block` → **Card** with heading + body (disclosure/notice panel)
  - shared: **Skeleton** for the streaming plan placeholder, **Tabs** not needed in
    MVP; transcript shell uses **Input**/**Textarea** + **Button** for the composer,
    **Card** for turn bubbles, **Badge** for the health mode indicator.
- **Rationale**: The boilerplate rule "put shadcn primitives in `src/components/ui`"
  plus principle VIII (no new deps) means the registry must be expressible with what
  shipped — verified: all six components map onto card/button/badge/table/separator/
  skeleton without a single new primitive. The map is data, so an unknown type is
  unreachable by construction (the Zod gate rejects it before the registry lookup).
- **Alternatives considered**: adding shadcn components (dialog/tabs) "for later"
  (YAGNI — principle VIII); rendering unknown types with a generic fallback card
  (explicitly forbidden — `contracts/ui-dsl.md` rule 2: never forward-compatible
  fallback rendering); a schema-driven generic renderer (over-engineering for six
  fixed shapes; harder to make accessible).

## R8 — Backend base URL via the boilerplate env pattern

- **Decision**: Add `NEXT_PUBLIC_AGENT_API_BASE_URL` to `src/shared/config/env.ts`
  (same `.url().optional().or(z.literal(""))` style as the existing service vars)
  and to `frontend/.env.example`. A small resolver in `features/shopping/api/
  agent-client.ts` treats empty/undefined as the localhost dev default
  `http://127.0.0.1:8000` (matching `FRONTEND_GUIDE.md` §2 and `contracts/http-api.md`
  conventions). The `/health` badge reuses TanStack Query in
  `features/shopping/hooks/use-health-badge.ts` calling `GET {base}/health`
  (`{status, mode}` per the frozen contract).
- **Rationale**: `env.ts` is the boilerplate's single validated boundary for public
  env (import-time Zod parse, `window.__RUNTIME_CONFIG__` runtime override for the
  Docker `infra/env.sh` flow) — bypassing it would break the documented deployment
  path where `NEXT_PUBLIC_*` values are injected at container start. A default keeps
  `npm run dev` zero-config while still env-driven in every other environment.
- **Alternatives considered**: `process.env` reads scattered in the feature
  (violates the validated-boundary pattern; breaks runtime-env injection); a Next
  rewrites/proxy entry in `next.config.ts` (hides the URL, adds server coupling, and
  `next.config.ts` is a read-local-docs-first file per `frontend/AGENTS.md`);
  requiring the var with no default (makes the boilerplate's zero-config dev flow
  fail for no safety gain).

## R9 — Testing strategy: three vitest layers, no E2E in MVP

- **Decision**: All tests in the existing vitest/jsdom setup (`vitest.config.ts`,
  `npm run test:run` inside `npm run verify`):
  1. **Pure unit**: frame parser fed hostile chunk splits (mid-frame, mid-separator,
     truncated final frame, junk lines); session-id rules (8–64 chars, uuid);
     reducer transition table for the turn state machine (IDLE → STREAMING → RENDER
     → IDLE, error paths).
  2. **Contract**: `validations/ui-plan-schema.test.ts` reads the five backend
     fixtures via fs — all must parse; programmatic mutations of each fixture
     (unknown `type`, catalog-foreign `productId`, bounds violations, disallowed
     action type, bad `planVersion`) must each fail with the expected issue; the
     catalog-id constant is cross-checked against
     `backend/app/catalog/data/headphones.json`.
  3. **Component (streaming harness)**: Testing Library renders
     `ShoppingPage`/`PlanRegion` with a mocked global `fetch` returning a
     `Response` whose body is a hand-built chunked `ReadableStream` (byte chunks
     emitted with deliberate splits); asserts stepper progression, delta
     accumulation, plan rendering per fixture, input lock/unlock, 409/404 handling,
     and error-frame behavior — the real turn pipeline, no network.
  NOT covered in MVP: real-browser E2E (Playwright recommended-but-not-installed by
  the boilerplate — deferred), real-mode latency timing tests (covered by design +
  manual verification per quickstart), visual regression, multi-tab concurrency
  automation (manual step in quickstart).
- **Rationale**: SC-006 requires the full suite to pass with no backend running;
  jsdom + a mocked chunked stream exercises the exact production code path (the
  same `fetch` + reader + parser + reducers) without sockets. Fixture fs-loading
  gives the contract teeth (R5). This mirrors the Phase 1 backend rationale
  (`specs/001/research.md` R9): assert the contract at the byte/frame level that
  the other side depends on.
- **Alternatives considered**: MSW (service-worker mocking adds setup for a single
  streaming endpoint a hand-built ReadableStream covers better — MSW streams are
  coarser to split per-chunk); Playwright now (install/config cost, flaky CI ports;
  the boilerplate explicitly defers it "when a project is ready"); Testing Library
  only without unit layer (chunk-boundary matrix is impractical to express in DOM
  assertions).

## R10 — Next.js 16 / React Compiler cautions; read-local-docs rule

- **Decision**: Treat `frontend/AGENTS.md`'s banner ("This is NOT the Next.js you
  know… Read the relevant guide in `node_modules/next/dist/docs/` before writing any
  code") as a hard precondition with an explicit task: before touching routing,
  metadata, `next.config.ts`, route handlers, caching, or build behavior, read the
  matching local doc from `frontend/node_modules/next/dist/docs/` (implementation-
  time step, first task of the US phases in tasks.md). Scope Next-specific surface to
  the minimum: one thin `(public)/shop/page.tsx` (metadata + feature export, per the
  playbook's "keep route files thin"), zero `next.config.ts` changes, zero route
  handlers, zero cacheComponents interaction (the page is a client-side experience;
  nothing in it needs server caching semantics).
- **Rationale**: The boilerplate runs Next **16.2.10** with `typedRoutes`,
  `reactCompiler: true`, `cacheComponents: true` — any of which may differ from
  training-data Next.js 13/14/15 conventions (the boilerplate's own docs
  (`docs/architecture.md` "Next 16 Patterns", README "Known constraint") call this
  out, including the Node `>=20.9.0` floor). React Compiler also restricts some
  manual-memoization/immutability patterns, so components follow plain hooks +
  immutable Redux state and let the compiler do its job. Reading the shipped docs
  is the only source that cannot drift from the installed version.
- **Alternatives considered**: relying on training-data Next knowledge (explicitly
  warned against by `frontend/AGENTS.md`); downgrading config flags to "safe"
  defaults (modifies owner boilerplate behavior for no reason); heavy use of server
  components/streaming SSR for the chat page (the turn loop is inherently
  client-stateful; adding server-render complexity buys nothing and multiplies the
  Next-16 unknowns this feature should be minimizing).
