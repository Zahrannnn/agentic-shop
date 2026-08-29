---
description: "Task list for feature implementation"
---

# Tasks: Frontend UI Renderer & Chat (Phase 2)

**Input**: Design documents from `/specs/002-frontend-ui-renderer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md,
plus the frozen inputs `../001-backend-agent-scaffold/contracts/http-api.md`,
`../001-backend-agent-scaffold/contracts/ui-dsl.md`, `FRONTEND_GUIDE.md`, and the
fixture corpus `backend/fixtures/ui-plans/`

**Tests**: INCLUDED — the boilerplate's handoff gate (`npm run verify`) runs the
vitest suite, and the constitution (principle V) requires the fixture contract
tests. Test tasks are written first within each story and must FAIL before their
implementation tasks run.

**Organization**: Tasks are grouped by user story (US1 P1 → US2 P1 → US3 P2 →
US4 P2 → US5 P3) so each story is independently implementable and testable.
Foundational carries the US4 contract test seed (the D8 double-sided obligation)
because the validation gate blocks everything downstream.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Frontend feature: `frontend/src/features/shopping/` (source),
  thin route `frontend/src/app/(public)/shop/page.tsx`, shared extensions in
  `frontend/src/shared/` — per plan.md Project Structure
- Backend fixtures/catalog are **read-only inputs** from `backend/` — no backend
  file is modified in this feature

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Boilerplate integration points and the Next 16 ground rules

- [ ] T001 Read the relevant Next.js 16 local guides in
      `frontend/node_modules/next/dist/docs/` — at minimum the app-router
      routing/layout and metadata guides (implementation-time step mandated by
      `frontend/AGENTS.md`: this Next version has breaking changes vs. training
      data). Record anything that contradicts the planned route pattern
      (`src/app/(public)/shop/page.tsx`) in `frontend/src/features/shopping/README.md`
      before writing route code. No config changes.
- [ ] T002 Scaffold the feature: `npm run corelia -- feature shopping` from
      `frontend/`; replace `.gitkeep` placeholders with the real files per plan.md
      as later tasks land; author `frontend/src/features/shopping/README.md`
      (ownership: chat turn lifecycle, plan registry, session lifecycle; consumers:
      `(public)/shop` route only)
- [ ] T003 [P] Extend env + routing constants: add
      `NEXT_PUBLIC_AGENT_API_BASE_URL` to the Zod schema in
      `frontend/src/shared/config/env.ts` (same `.url().optional().or(z.literal(""))`
      style as the existing service vars) and to `frontend/.env.example`; add
      `shop: "/shop"` to `frontend/src/shared/constants/routes.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contract mirror, frame parser, client state — nothing story-level
starts before these exist

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Create `frontend/src/features/shopping/constants/lifecycle.ts`:
      `LIFECYCLE_STAGES` (intent_parsed, searching, found_n, researching, ranking,
      building_ui, in contracted order), `ALLOWED_ACTIONS_BY_TYPE` (per
      contracts/ui-dsl.md), `SESSION_ID_MIN = 8`, `SESSION_ID_MAX = 64`,
      `MESSAGE_MAX = 2000`, `STORAGE_KEY` for session persistence
- [ ] T005 [P] Create `frontend/src/features/shopping/utils/catalog-refs.ts`:
      `CATALOG_PRODUCT_IDS: ReadonlySet<string>` literal mirroring the 28 ids in
      `backend/app/catalog/data/headphones.json` (document the regeneration rule in
      a comment)
- [ ] T006 [P] Create `frontend/src/features/shopping/validations/fixtures.ts`:
      test-only `loadUiPlanFixtures()` reading the five JSONs from
      `../../../../backend/fixtures/ui-plans/` via `node:fs` (monorepo-root
      assumption, research.md R5); fail loudly if a file is missing
- [ ] T007 [US4] Create `frontend/src/features/shopping/validations/ui-plan-schema.test.ts`
      (write FIRST, must FAIL before T008): all five backend fixtures parse through
      `uiPlanSchema`; the mutation matrix rejects — unknown `root.type`, grid with
      0 and 7 productIds, picker with 1 and 5 options, comparison with 1 and 4 ids,
      two `choose` actions, a `text_block` carrying actions, non-catalog
      `productId`, picker option without a matching action, `planVersion: "2"`,
      empty `sessionId`, `turnId: 0`
- [ ] T008 Implement `frontend/src/features/shopping/validations/ui-plan-schema.ts`
      per data-model.md (envelope, discriminated union over the six component
      schemas with bounds, allowed-action sets, catalog refinement, picker-option ↔
      action super-refinement) and export the `z.infer` types — T007 goes green
- [ ] T009 [P] [US1] Create `frontend/src/features/shopping/api/sse-frame-parser.test.ts`
      (write FIRST, must FAIL before T010): full valid stream parses in order;
      chunk splits at every boundary class (before/inside `event:` line, inside
      data JSON, inside the `\n\n` separator) yield identical sequences; final
      frame without trailing blank line parses on `flush()`; unparsable data line →
      `ignored`, no throw; unknown event name → `ignored`
- [ ] T010 [US1] Implement `frontend/src/features/shopping/api/sse-frame-parser.ts`
      per data-model.md (pure accumulate/split/flush parser) — T009 goes green
- [ ] T011 [P] [US1] Create `frontend/src/features/shopping/store/transcript-slice.test.ts`
      (write FIRST, must FAIL before T012): reducer transition table —
      turnStarted locks (`isStreaming` true), turnStatus appends idempotently in
      order, turnDelta appends answer text, turnPlanAccepted/Rejected set plan or
      planError, turnCompleted/turnFailed/turnDropped set terminal and unlock,
      busyRejected marks failed with retry affordance; unknown turn id is a no-op
- [ ] T012 Implement `frontend/src/features/shopping/store/session-slice.ts` and
      `frontend/src/features/shopping/store/transcript-slice.ts` per data-model.md,
      register both in `frontend/src/shared/store/store.ts`, and add the
      sessionStorage persistence/rehydration (single `STORAGE_KEY`, session +
      transcript) — T011 goes green

**Checkpoint**: Foundation ready — contract mirror proven against real fixtures,
parser proven against hostile splits, client state machine unit-green; user
stories can proceed in priority order

---

## Phase 3: User Story 1 — Chat turn lifecycle over the streaming contract (Priority: P1) 🎯 MVP

**Goal**: Send a message → POST via fetch + ReadableStream → stepper walks the
stages → deltas accumulate → plan placeholder region → terminal frame unlocks input;
chunk splits are invisible

**Independent Test**: With the backend in mock mode, one complete request shows the
full ordered lifecycle with lock/unlock; the mocked chunked-stream harness proves
identical parses under every split class

### Tests for User Story 1 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T013 [P] [US1] Create `frontend/src/features/shopping/hooks/use-agent-turn.test.tsx`:
      mocked global `fetch` returning a hand-built chunked `ReadableStream`
      (`Response` with byte chunks emitted across frame boundaries); asserts —
      request body shape (`session_id` 8–64 chars, `message`, `ui_action: null`,
      `resume: false`), statuses dispatch in order, deltas join, `ui_update` data
      flows through `uiPlanSchema` to `turnPlanAccepted`, `turn_end` completes and
      unlocks, `error` frame fails with message, stream closing without a terminal
      frame dispatches `turnDropped`, non-200 mapping (404 → resume-recovery hook
      point, 409 → busyRejected, 422 → clean failure)
- [ ] T014 [P] [US1] Create `frontend/src/features/shopping/components/__tests__/ShoppingPage.test.tsx`:
      renders the page with the harness stream and asserts — input disabled between
      send and terminal, stepper advances stage-by-stage, answer text appears
      incrementally, plan placeholder region present, second send attempt while
      streaming is refused

### Implementation for User Story 1

- [ ] T015 [US1] Implement `frontend/src/features/shopping/api/agent-client.ts`:
      base-URL resolver (env value, empty → `http://127.0.0.1:8000`), `postChat()`
      using native `fetch` + `response.body.getReader()` + TextDecoder feeding
      `sse-frame-parser`, JSON-reads non-200 bodies into typed results; **no
      AbortController timeout on the stream** (US5 long-latency requirement);
      `getHealth()` for `{status, mode}`
- [ ] T016 [US1] Implement `frontend/src/features/shopping/hooks/use-agent-turn.ts`
      per data-model.md (`sendText`, re-entry guard, parser events → validation
      gate → transcript actions) — T013 goes green
- [ ] T017 [P] [US1] Implement `frontend/src/features/shopping/components/StatusStepper.tsx`:
      six-stage indicator driven by `stagesSeen` (no stage is assumed; the stepper
      shows honest progress through gaps — presentational, no timers)
- [ ] T018 [P] [US1] Implement `frontend/src/features/shopping/components/MessageComposer.tsx`:
      labeled textarea + send button, disabled while `isStreaming` (FR-011),
      enforces `MESSAGE_MAX`, keyboard operable
- [ ] T019 [US1] Implement `frontend/src/features/shopping/components/TranscriptView.tsx`:
      turn list (user bubble + agent turn with stepper, answer text, plan region
      placeholder, error line); transcript persists across turns, plan region is
      the only replaced area (FR-008)
- [ ] T020 [US1] Implement `frontend/src/features/shopping/components/ShoppingPage.tsx`
      (feature shell) and export it plus `useAgentTurn` from
      `frontend/src/features/shopping/index.ts`
- [ ] T021 [US1] Create the thin route `frontend/src/app/(public)/shop/page.tsx`
      (metadata + `<ShoppingPage />` from `@/features/shopping`, per the
      playbook's thin-route rule) — T014 goes green

**Checkpoint**: US1 fully works against the mock backend: one request shows the
complete streamed lifecycle with lock/unlock, chunk-split-proof (T009 matrix green)

---

## Phase 4: User Story 2 — Plan renderer registry behind a validation gate (Priority: P1)

**Goal**: Every `ui_update` renders through the Zod gate + fixed registry of six
components; invalid plans never render; full replace semantics

**Independent Test**: Each of the five fixtures renders through `PlanRegion`; each
contract-violating mutation shows `PlanErrorState` and nothing else

### Tests for User Story 2 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T022 [P] [US2] Create `frontend/src/features/shopping/components/__tests__/PlanRegion.test.tsx`:
      each of the five fixtures (via `loadUiPlanFixtures()`) renders its component
      with the fixture's own strings visible (grid title, picker question, table
      headers, details quotes flag, cart total); each mutated invalid plan renders
      `PlanErrorState` only and leaves the transcript untouched (assert via mock
      store state); consecutive different plans fully replace (no stale DOM from
      the first plan)

### Implementation for User Story 2

- [ ] T023 [US2] Implement `frontend/src/features/shopping/components/registry.ts`
      (fixed `Record<PlanComponent["type"], ComponentType>` — no fallback entry) and
      `frontend/src/features/shopping/components/PlanRegion.tsx` (gate: parse →
      render via registry; reject → `PlanErrorState` with reason) — T022 goes green
      once components land
- [ ] T024 [P] [US2] Implement `frontend/src/features/shopping/components/ProductGridCard.tsx`
      (Card + rank Badge + per-card compare/details/add_to_cart Buttons wired to an
      `onAction(UIAction)` prop) and `PreferencePicker.tsx` (question Card + one
      outline Button per option, each dispatching its matching `select_preference`
      action) — shadcn primitives only (research.md R7)
- [ ] T025 [P] [US2] Implement `frontend/src/features/shopping/components/ComparisonTable.tsx`
      (Table from attributes × products, single `choose` CTA) and
      `ProductDetails.tsx` (specs Card, Separator groups, quotes list when
      `showQuotes`)
- [ ] T026 [P] [US2] Implement `frontend/src/features/shopping/components/CartView.tsx`
      (items Table, quantities, `totalUsd`, per-item remove Button) and
      `TextBlock.tsx` (optional heading + body notice card)
- [ ] T027 [US2] Implement `frontend/src/features/shopping/components/PlanErrorState.tsx`:
      deliberate invalid-plan UI (icon + "This result couldn't be displayed" +
      reason reserved for dev view); includes the designed empty state variant for
      in-bounds empties; all rendered controls carry accessible names

**Checkpoint**: US2 green — five fixtures render, five mutation classes show the
error state, full-replace proven

---

## Phase 5: User Story 3 — Interactive shopping loop with session lifecycle (Priority: P2)

**Goal**: Plan taps and free text both drive turns; session id stable per
conversation; resume/404 fresh-start flow; 409 busy affordance

**Independent Test**: In one mock-mode conversation: recommendation → chip answer →
compare → details → add-to-cart → remove; reload mid-conversation continues the
session; restarted backend yields the expiry notice + fresh session

### Tests for User Story 3 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T028 [P] [US3] Extend `frontend/src/features/shopping/hooks/use-agent-turn.test.tsx`:
      `sendAction` posts `{session_id, message: "", ui_action: <verbatim object>,
      resume: false}`; a tapped picker chip streams a normal follow-up turn;
      `resumePendingText` posts `resume: true` and on 404 dispatches the expiry
      flow (new `session_id`, resend without resume) asserting both request bodies;
      409 response marks the turn failed with the retry affordance and unlocks

### Implementation for User Story 3

- [ ] T029 [US3] Extend `frontend/src/features/shopping/hooks/use-agent-turn.ts`:
      `sendAction(action)` and `resumePendingText(message)` per data-model.md —
      T028 goes green
- [ ] T030 [US3] Wire the loop: `frontend/src/features/shopping/components/ShoppingPage.tsx`
      passes `sendAction` into `PlanRegion` → registry components' `onAction`
      (tapping any plan control starts a turn; composer sends free text through the
      same lock)
- [ ] T031 [US3] Implement `frontend/src/features/shopping/components/SessionExpiredNotice.tsx`
      (small inline transcript notice: "session expired — starting fresh") and hook
      it to the 404 recovery dispatch
- [ ] T032 [US3] Implement the 409 retry affordance in
      `frontend/src/features/shopping/components/MessageComposer.tsx` (disabled
      state + visible "try again" hint when the last turn failed busy)
- [ ] T033 [US3] Add US3 acceptance coverage to
      `frontend/src/features/shopping/components/__tests__/ShoppingPage.test.tsx`:
      full loop with mocked streams (grid tap → comparison tap → details tap →
      cart tap → remove tap) each streaming as a normal turn with the same
      `session_id`; positional free text ("compare the first two") is sent
      verbatim as `message` (client resolves nothing)

**Checkpoint**: US3 green — the full MVP acceptance flow runs inside one
conversation with session lifecycle handled

---

## Phase 6: User Story 4 — Mirrored plan contract proven by fixture tests (Priority: P2)

**Goal**: The D8 double-sided obligation is demonstrably closed: client schema
accepts the backend's five fixtures and rejects every known-bad class; catalog
mirror cannot drift

**Independent Test**: `npm run test:run` passes with no backend running; the
contract test file alone proves accept/reject behavior

- [ ] T034 [US4] Complete the rejection matrix and catalog cross-check in
      `frontend/src/features/shopping/validations/ui-plan-schema.test.ts`: extend
      T007's matrix with the remaining per-component disallowed-action cases
      (e.g. `compare` on a `cart_view`, `select_preference` on a `product_grid`)
      and add the test reading `backend/app/catalog/data/headphones.json` (via the
      T006-style fs path) asserting `CATALOG_PRODUCT_IDS` matches it exactly — any
      backend catalog change fails here until `utils/catalog-refs.ts` is regenerated
- [ ] T035 [US4] Add render-through-gate coverage: assert in
      `frontend/src/features/shopping/components/__tests__/PlanRegion.test.tsx`
      that the five fixtures' renders each expose their allowed actions as
      enabled controls (grid: 3 buttons/card labels; picker: one chip per option;
      comparison: exactly one choose CTA; cart: one remove per item; details/text:
      none) — the wire-level loop surface of FR-009

**Checkpoint**: US4 green — contract mirror has teeth on both sides, and the
registry exposes exactly the contracted action surface

---

## Phase 7: User Story 5 — Environment integration, latency tolerance & polish (Priority: P3)

**Goal**: Health badge, env-driven base URL, long-gap tolerance, deliberate
error/empty states, WCAG 2.2 AA basics, docs

**Independent Test**: Badge flips with the backend's reported mode; a stream with
multi-second silent gaps completes; keyboard-only pass and badge check per
quickstart.md step 4/8

### Tests for User Story 5 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T036 [P] [US5] Create `frontend/src/features/shopping/hooks/use-health-badge.test.tsx`:
      mocks `getHealth` → badge renders `mock` / `real`; rejected fetch →
      deliberate "unreachable" state, no crash
- [ ] T037 [P] [US5] Extend the harness in
      `frontend/src/features/shopping/hooks/use-agent-turn.test.tsx` with a
      delayed-chunk stream (e.g. 2 s gaps via fake timers): the turn stays locked,
      stepper keeps last honest stage, and the turn completes only when the stream
      terminates — proves no client timeout exists (FR-013/US5)

### Implementation for User Story 5

- [ ] T038 [US5] Implement `frontend/src/features/shopping/hooks/use-health-badge.ts`
      (TanStack Query over `getHealth()`, `staleTime` 30 s, `mock|real|unknown`)
      and render the mode Badge in `frontend/src/features/shopping/components/ShoppingPage.tsx`
      — T036 goes green
- [ ] T039 [US5] Polish + accessibility pass across
      `frontend/src/features/shopping/components/`: semantic regions (form landmark
      for composer, log region for transcript), visible focus on every control,
      aria-live for streaming answer text, reduced-motion respect for the stepper,
      empty-state copy for the empty cart and unreachable-backend cases
- [ ] T040 [P] [US5] Update `frontend/README.md` (Routes list: add `/shop`;
      Environment: `NEXT_PUBLIC_AGENT_API_BASE_URL`) and
      `frontend/src/features/shopping/README.md` (feature notes from T001/T002) —
      keep `specs/002-frontend-ui-renderer/quickstart.md` as the source of truth

**Checkpoint**: US5 green — operable without credentials, honest under real-mode
latency, accessible, documented

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Gates, joint smoke, constitution sweep

- [ ] T041 Run the full frontend gate and fix findings:
      `cd frontend && npm run verify` (lint → typecheck → test:run → build);
      zero TypeScript `any` in feature code, zero new runtime dependencies
- [ ] T042 Joint smoke per `specs/002-frontend-ui-renderer/quickstart.md` steps 2–7:
      backend in mock mode + `npm run dev`, walk the MVP loop (grid → chips →
      compare → details → cart), reload-resume, backend-restart expiry; record
      results; also re-run the backend's own gates once
      (`cd backend && uv run ruff check . && uv run pytest`) to prove the shared
      fixture corpus is still green on both sides
- [ ] T043 Final constitution compliance sweep: no backend file modified (fixtures
      and catalog are read-only inputs), no secrets committed (`.env.local`
      gitignored), no new runtime deps in `frontend/package.json`, no plan-patching
      code paths, no fallback rendering of unknown plan types, deviations RTK/npm
      documented in `specs/002-frontend-ui-renderer/research.md` R2/R3 (constitution
      I, V, VI, VIII)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T001's doc read gates
  T021 (route work), T003 gates everything env-consuming
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
  (T005 → T008; T006+T005 → T007 → T008; T004 → T008/T012; T010 and T012 are the
  pipeline's two halves)
- **US1 (Phase 3)**: Needs Foundational (parser T010, slices T012); delivers the
  working turn loop
- **US2 (Phase 4)**: Needs US1's `PlanRegion` placeholder (T019) and the gate
  schema (T008); components are independent of US3
- **US3 (Phase 4→5)**: Needs US2's rendered controls (their `onAction` props land
  in T024–T026); the loop wiring (T030) is the junction
- **US4 (Phase 6)**: Seed written in Foundational (T007); completes after US2 so
  render-through-gate assertions (T035) have components to assert on
- **US5 (Phase 7)**: Needs US1's page shell; polish tasks touch US2/US3 files —
  run after them
- **Polish (Phase 8)**: After all stories

### User Story Dependencies

- **US1 (P1)**: Foundational only — no cross-story dependency
- **US2 (P1)**: Needs US1's transcript shell; independently testable via fixture
  renders
- **US3 (P2)**: Needs US1 (turn pipeline) + US2 (rendered actions); independently
  testable with mocked streams
- **US4 (P2)**: Schema seed blocks everything (Foundational); story completion
  needs US2 components for T035 only
- **US5 (P3)**: Needs US1's shell; touches all feature files — last

### Within Each User Story

- Tests first (must FAIL), then implementation, then scenario tests green
- Pure modules (parser, slices, schema) before hooks; hooks before components;
  components before the route
- The validation gate (T008) precedes every consumer

### Parallel Opportunities

- Setup: T002 ∥ T003 (T001 any time before T021)
- Foundational: T004 ∥ T005 ∥ T006; test files T007/T009/T011 are different files —
  parallelizable once their imports exist as types
- US2: T024 ∥ T025 ∥ T026 (six components, six files); US5: T036 ∥ T037
- Story phases touch overlapping page files — sequential by phase, parallel only
  where [P] is marked

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 US1 → Phase 4 US2 → **STOP**: `npm run test:run` green + one manual
   mock-mode conversation showing the streamed recommendation grid proves the
   product's core claim
3. Demo-ready before the loop wiring exists

### Incremental Delivery

1. Foundational → US1 (live turn loop) → US2 (rendered plans) → US3 (interactive
   MVP acceptance flow) → US4 (contract proven both sides) → US5 (operational
   polish) → Polish
2. Every checkpoint leaves `npm run verify` green and the app usable against the
   mock backend

### Notes

- All development happens against the mock backend (deterministic, sub-second);
  real mode is exercised only by the optional manual step (quickstart step 4.8)
- The contract tests are the canary for backend drift — if they fail after a
  backend change, the fix is a schema review on both sides, never loosening the
  mirror silently (constitution V)
- Do not read `frontend/node_modules/next/dist/docs/` selectively later — T001 is
  the precondition for any routing/metadata/config edit (frontend/AGENTS.md)
- Commit after each task or logical group; Conventional Commits per AGENTS.md
