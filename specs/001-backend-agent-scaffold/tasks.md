---
description: "Task list for feature implementation"
---

# Tasks: Agentic Shopping Backend (Phase 1 Scaffold)

**Input**: Design documents from `/specs/001-backend-agent-scaffold/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, contracts/ui-dsl.md, quickstart.md

**Tests**: INCLUDED — the project constitution (principle VII) and AGENTS.md
quality gates require pytest coverage (scorer, tools, DSL validation, graph
happy path). Test tasks are written first within each story and must FAIL
before their implementation tasks run.

**Organization**: Tasks are grouped by user story (US1 P1 → US2 P2 → US3 P2 →
US5 P2 → US4 P3) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Backend service: `backend/app/` (source), `backend/tests/` (tests),
  `backend/fixtures/` (shared contract corpus) — per plan.md Project Structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [ ] T001 Create `backend/pyproject.toml` managed by uv: runtime deps
      (fastapi, uvicorn, langgraph, langchain-core, langchain-openai, pydantic,
      pydantic-settings), dev deps (pytest, pytest-asyncio, httpx, ruff),
      `[tool.ruff]` line-length + lint config, `[tool.pytest.ini_options]`
      (asyncio_mode = auto, testpaths = tests)
- [ ] T002 Create package skeleton per plan.md: `backend/app/` with empty
      `__init__.py` in `app/`, `app/llm/`, `app/catalog/`, `app/catalog/data/`,
      `app/ranking/`, `app/tools/`, `app/graph/`, `app/dsl/`, `app/api/`;
      `backend/tests/`; `backend/fixtures/ui-plans/`
- [ ] T003 [P] Create `backend/.env.example` documenting `LLM_MODE` (default
      `mock`), `LLM_MODEL`, `OPENCODE_BASE_URL`, `OPENCODE_API_KEY` (placeholder
      values only) and add `.env` to `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, catalog, LLM factory, DSL contract — nothing story-level
starts before these exist

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Implement env-driven `Settings` in `backend/app/config.py`
      (pydantic-settings): `LLM_MODE="mock"`, `LLM_MODEL`, `OPENCODE_BASE_URL`,
      `OPENCODE_API_KEY`; fail-fast helper `require_real_config()` for
      `LLM_MODE=real`
- [ ] T005 [P] Implement catalog models in `backend/app/catalog/models.py`:
      `ReviewScores` (comfort/anc/sound/battery/value, 0–5), `Product` with all
      fields and enum `ANCType` per data-model.md
- [ ] T006 [P] Author curated dataset `backend/app/catalog/data/headphones.json`:
      exactly 28 headphones across $49–$549; flights scenario with 4 genuine
      winners (battery king ≥60h, comfort king lightest + top comfort score,
      ANC king top anc score, value pick best score-per-dollar under $200);
      every item has 4–6 short quotes per data-model.md
- [ ] T007 Implement `backend/app/catalog/loader.py`: `load_catalog()` validating
      every record via `Product` (loud failure on malformed/duplicate ids) +
      normalization helpers (`min_max(values, invert=False)`, `anc_ordinal()`)
      used by the scorer
- [ ] T008 Implement `backend/app/llm/client.py` (constitution II & IV):
      `get_llm()` factory returning `ChatOpenAI(model, api_key, base_url,
      temperature=0)` or `MockChatLLM` when `LLM_MODE=mock`; `MockChatLLM` with
      deterministic `with_structured_output` returning canned instances keyed by
      schema type + test knobs; `call_structured(llm, Model, messages)` wrapper
      with exactly one validation-error retry then `StructuredOutputError`
- [ ] T009 Implement DSL schemas in `backend/app/dsl/models.py` per
      contracts/ui-dsl.md: `UIPlan`, `ComponentNode` (typed union of the 6 MVP
      component prop models), `UIAction`; camelCase wire serialization
      (`alias_generator=to_camel`, `populate_by_name=True`)
- [ ] T010 Implement `backend/app/dsl/validate.py`: catalog-aware validation
      (known component types, productIds exist, actions ⊆ allowed set, bounds)
      + `serialize_plan()`; invalid plans raise `PlanValidationError`
- [ ] T011 [P] Author fixture corpus `backend/fixtures/ui-plans/`:
      `product-grid-flights.json`, `preference-picker-category.json`,
      `comparison-two.json`, `product-details.json`, `cart-one-item.json`
      (wire format per contracts/ui-dsl.md)
- [ ] T012 Implement API request/event models in `backend/app/api/schemas.py`:
      `ChatRequest` (session_id, message 1–2000, optional ui_action), event data
      models for `status`/`message_delta`/`ui_update`/`turn_end`/`error` with
      stage enum and error codes per contracts/http-api.md
- [ ] T013 Implement `backend/tests/conftest.py`: mock-mode env fixture
      (no credentials), `load_catalog` fixture, httpx `AsyncClient(transport=
      ASGITransport(app))` helper, `ScriptedFakeLLM` injection hook overriding
      `get_llm` for fault-injection tests

**Checkpoint**: Foundation ready — mock LLM, catalog, DSL contract, and test
harness all exist; user stories can proceed in priority order

---

## Phase 3: User Story 1 — Complete shopping request end-to-end (Priority: P1) 🎯 MVP

**Goal**: One complete request → streamed lifecycle → deterministic top-3 with
attribute-grounded narration → validated product grid plan → turn_end

**Independent Test**: POST one complete message to `/api/chat` in mock mode;
assert ordered status stages, message deltas, one valid `ui_update`, one
`turn_end`; top-3 within budget and order == scorer order

### Tests for User Story 1 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T014 [P] [US1] Create `backend/tests/test_scorer.py`: pure-scorer unit
      tests — contributions sum to score, weight normalization (incl. all-zero →
      uniform), min-max inversion for weight_g, missing attr → 0.5 neutral,
      anc ordinal ordering, tie-break by product_id, identical output across
      repeated calls
- [ ] T015 [P] [US1] Add search-tool tests to `backend/tests/test_tools.py`:
      category filter, price ceiling, attribute filters, empty-result behavior
      (relaxation handed off to caller) against the real fixture catalog

### Implementation for User Story 1

- [ ] T016 [US1] Implement pure `score_products(candidates, weights)` in
      `backend/app/ranking/scorer.py` per research.md R6 (no I/O, no clock,
      no randomness)
- [ ] T017 [US1] Implement research tools in `backend/app/tools/research.py`:
      `get_product_specs(id)`, `get_product_reviews(id)` returning pre-scored
      summaries + quotes from the catalog (no runtime NLP)
- [ ] T018 [US1] Implement `backend/app/tools/search.py`:
      `search_products(category, max_price, attributes)` over the loaded catalog
- [ ] T019 [US1] Implement node output models in `backend/app/graph/schemas.py`:
      `IntentExtraction`, `PreferenceWeights`, `Narration`, `PlanSelection` per
      data-model.md
- [ ] T020 [US1] Implement `backend/app/graph/state.py` (`ShoppingState`
      TypedDict) and `backend/app/graph/builder.py` (fixed 7-node backbone,
      `MemorySaver`, `thread_id` = session id; conditional edge stubbed to
      always "proceed" until US2)
- [ ] T021 [US1] Implement proceed-path nodes in `backend/app/graph/nodes.py`:
      `intent` (call_structured IntentExtraction, merge into UserIntent),
      `search`, `research`, `recommend` (PreferenceWeights via call_structured →
      pure scorer → top-3), `ui_plan` (assemble product_grid from ranked data via
      PlanSelection), `respond` (stream narration text deltas via
      `get_stream_writer`); each node emits `status` events at stage boundaries
- [ ] T022 [US1] Implement `backend/app/api/routes.py`: `GET /health` and
      `POST /api/chat` returning `StreamingResponse` that drives
      `graph.astream(stream_mode="custom")` and frames D7 SSE events
      (status → message_delta → ui_update → turn_end) per contracts/http-api.md;
      wire into `backend/app/main.py`
- [ ] T023 [US1] Add happy-path contract tests to
      `backend/tests/test_api_sse.py`: exact frame order and event names for a
      complete request; plan frame matches `product-grid-flights` fixture
      semantics; `turn_end` is last frame

**Checkpoint**: US1 fully works in mock mode via HTTP; scorer and tools are
unit-green

---

## Phase 4: User Story 2 — Clarifying an incomplete request (Priority: P2)

**Goal**: Rule-based clarify gate asks at most once with chips; answered
requests run to completion; budget assumption and contradictions disclosed

**Independent Test**: Category-less message → exactly one picker turn; then an
answer → full US1 outcome with no second question

### Tests for User Story 2 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T024 [P] [US2] Create `backend/tests/test_clarify_gate.py`: exhaustive
      rule-table tests — missing category → ask; unknown category → ask;
      known category → proceed; `asked_clarification=True` → always proceed;
      missing budget → proceed with default cap + assumption recorded; zero
      matching products under constraints → contradiction flag

### Implementation for User Story 2

- [ ] T025 [US2] Implement `clarify_gate(state)` as a pure function and
      `ui_agent_ask` node (deterministic `preference_picker` plan from catalog
      categories; question via `message_delta`) in `backend/app/graph/nodes.py`
- [ ] T026 [US2] Wire the single conditional edge in
      `backend/app/graph/builder.py`: `clarify_gate → (ask) ui_agent_ask → END`
      / `(proceed) search`; answer turns resume from checkpoint and proceed
- [ ] T027 [US2] Add disclosure behavior to `respond` in
      `backend/app/graph/nodes.py`: state assumptions (budget cap applied) and
      contradiction flags as part of the answer text per spec US2 scenarios 3–4
- [ ] T028 [US2] Add US2 acceptance scenarios to
      `backend/tests/test_graph_happy_path.py`: ask → answer → complete flow;
      at-most-one-question invariant; budget-assumption turn completes without
      asking

**Checkpoint**: Incomplete requests are handled deterministically end-to-end

---

## Phase 5: User Story 3 — Every turn carries a validated UI plan (Priority: P2)

**Goal**: Validation-before-emission on every turn path; fixtures are the
enforced contract; full-replace semantics with per-turn identity

**Independent Test**: Every completed turn in mock mode emits a plan that
round-trips through the DSL models and matches a fixture semantically

### Tests for User Story 3 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T029 [P] [US3] Create `backend/tests/test_dsl.py`: every fixture in
      `backend/fixtures/ui-plans/` validates via `dsl.validate`; known-bad
      mutations (unknown type, foreign productId, out-of-bounds list,
      disallowed action, bad planVersion) each raise `PlanValidationError`;
      camelCase round-trip preserves semantics

### Implementation for User Story 3

- [ ] T030 [US3] Enforce validation-before-emission in both plan-producing
      nodes in `backend/app/graph/nodes.py` (`ui_plan`, `ui_agent_ask`):
      `PlanValidationError` → `error` protocol event, never an invalid
      `ui_update`
- [ ] T031 [US3] Add monotonic `turn_id` tracking to `ShoppingState` in
      `backend/app/graph/state.py` (counter increments per turn — no wall
      clock) and stamp it into every plan envelope
- [ ] T032 [US3] Add US3 acceptance coverage to
      `backend/tests/test_graph_happy_path.py`: each turn type (recommend,
      clarify, compare, details, cart) emits a schema-valid full plan

**Checkpoint**: The plan contract is machine-enforced on every path

---

## Phase 6: User Story 5 — Keyless, deterministic, fail-clean operation (Priority: P2)

**Goal**: Whole pipeline + suite run with no credentials; malformed model
output retried once then one clean error; rankings byte-identical

**Independent Test**: Kill network + unset keys → suite green; same request in
two fresh sessions → identical rankings; fault-injected LLM → 1 retry + 1
error frame

### Tests for User Story 5 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T033 [P] [US5] Add fault-injection tests to
      `backend/tests/test_graph_happy_path.py` using `ScriptedFakeLLM` from
      conftest: malformed structured output → exactly one retry carrying the
      validation error → second failure → single `error` frame
      (`code=structured_output`), turn ends, no raw model text in any frame
- [ ] T034 [P] [US5] Add determinism tests to
      `backend/tests/test_graph_happy_path.py`: same complete request to 2
      fresh sessions × 3 runs in mock mode → identical ranked id lists and
      identical `Narration` selections

### Implementation for User Story 5

- [ ] T035 [US5] Implement startup fail-fast in `backend/app/config.py` +
      `backend/app/main.py`: `LLM_MODE=real` without `OPENCODE_API_KEY`/
      `LLM_MODEL` raises at app creation with a clear message
- [ ] T036 [US5] Add config tests to `backend/tests/test_tools.py` (or a new
      `backend/tests/test_config.py`): mock default without env vars;
      real-mode-without-key failure; no secret values ever echoed by `/health`

**Checkpoint**: Operational guarantees (constitution II, III, IV) are
demonstrated by tests, not claims

---

## Phase 7: User Story 4 — Multi-turn follow-ups in one session (Priority: P3)

**Goal**: Compare/details/re-rank/cart follow-ups resolve positional and
demonstrative references from session state; cart is per-session

**Independent Test**: Recommendation turn → "compare the first two" → exact
top-2 ids in a comparison_table; preference change re-ranks; add-to-cart then
get-cart shows exactly that item

### Tests for User Story 4 (write FIRST, must FAIL before implementation) ⚠️

- [ ] T037 [P] [US4] Add cart-tool tests to `backend/tests/test_tools.py`:
      add (idempotent quantity merge), remove, get, unknown product rejection,
      totals from catalog prices

### Implementation for User Story 4

- [ ] T038 [US4] Implement `backend/app/tools/cart.py`: per-session mock cart
      ops (`add_to_cart`, `remove_from_cart`, `get_cart`) reading/writing the
      cart block of session state
- [ ] T039 [US4] Extend `intent` node in `backend/app/graph/nodes.py` to
      resolve follow-ups against session state: `ui_action` payloads, positional
      references ("the first two" → `selected_ids` from last `ranked`),
      preference-change and refine requests merged into `UserIntent`
- [ ] T040 [US4] Extend `ui_plan` node in `backend/app/graph/nodes.py` to
      assemble `comparison_table`, `product_details`, and `cart_view` plans
      from `selected_ids`/cart state (PlanSelection drives component choice)
- [ ] T041 [US4] Add US4 acceptance scenarios to
      `backend/tests/test_graph_happy_path.py`: compare-first-two → exact ids;
      comfort-over-sound re-rank may reorder with explanation; add-to-cart →
      cart_view contents; references resolve across ≥4 turns in one session

**Checkpoint**: Full MVP acceptance flow (search → refine → inspect → compare
→ recommend → cart) runs inside one session

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Concurrency guard, docs, final gates

- [ ] T042 Implement per-session busy guard in `backend/app/api/routes.py`:
      in-flight turn per `session_id` → second concurrent request gets
      `409 {"detail":"turn_in_flight"}`; add test to
      `backend/tests/test_api_sse.py` (FR-016)
- [ ] T043 [P] Validate `backend/README.md` quickstart section against
      `specs/001-backend-agent-scaffold/quickstart.md` commands (copy runnable
      snippets; keep specs as source of truth)
- [ ] T044 Run full quality gates and fix findings: `cd backend && uv sync &&
      uv run ruff check . && uv run ruff format --check . && uv run pytest`;
      then execute `specs/001-backend-agent-scaffold/quickstart.md` steps 2–6
      manually and record results
- [ ] T045 Final constitution compliance sweep: no `frontend/` files created,
      no edits to `PRD.md`/`DECISIONS.md`, no secrets in tree, temperature
      literal 0 only inside `backend/app/llm/client.py` (constitution I, II, VI)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
  (T006 before T007; T008 before any story test that injects fakes; T009–T011
  before US3/US1 plan emission)
- **US1 (Phase 3)**: First story — everything else extends its pipeline
- **US2 (Phase 4)**: Needs US1's proceed-path nodes to exist
- **US3 (Phase 5)**: Needs both plan-producing paths (US1 grid + US2 picker)
  to guard emission
- **US5 (Phase 6)**: Needs the wrapper (T008) and any completed story path;
  logically after US3 so fault tests observe plan emission too
- **US4 (Phase 7)**: Needs US1 ranking + US2 state accumulation; extends nodes
  and tools only
- **Polish (Phase 8)**: After all stories

### User Story Dependencies

- **US1 (P1)**: Foundational only — no cross-story dependency
- **US2 (P2)**: Extends US1's graph; independently testable via its own
  scenarios
- **US3 (P2)**: Guards all plan paths; its fixture tests (T029) are runnable
  right after Foundational (T009–T011)
- **US5 (P2)**: Cross-cutting guarantees; tests independent of US4
- **US4 (P3)**: Depends on US1 + US2 state; independent of US5

### Within Each User Story

- Tests first (must FAIL), then models/tools, then nodes/routes, then
  scenario tests green
- Pure functions (scorer, clarify_gate) before graph nodes that call them
- Node implementation before route framing; routes before SSE contract tests
  can pass

### Parallel Opportunities

- Setup: T003 parallel with T001–T002
- Foundational: T005 ∥ T006 ∥ T013; T011 after T009; T012 ∥ T008
- Story test files (T014, T015, T024, T029, T033, T034, T037) are all
  different files — parallelizable once their foundations exist
- Stories US2/US3/US5/US4 phases touch overlapping node files — sequential by
  phase, parallel only where [P] is marked

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup → Phase 2 Foundational
2. Phase 3 US1 → **STOP**: `uv run pytest tests/test_api_sse.py` + one curl of
   `/api/chat` proves the core loop
3. Demo-ready even before clarify/follow-ups exist

### Incremental Delivery

1. Foundational → US1 (core loop demo) → US2 (graceful incomplete input) →
   US3 (contract enforced) → US5 (operational guarantees) → US4 (full MVP
   acceptance flow) → Polish
2. Every checkpoint leaves `uv run pytest` green and the server runnable in
   mock mode

### Notes

- All implementation happens in mock mode; real gateway config is exercised
  only by config tests (never live in CI)
- Determinism invariants (T014, T034) are the canary for any future change —
  keep them strict
- Commit after each task or logical group; Conventional Commits per AGENTS.md
