# Research & Decisions — Agentic Shopping Backend (Phase 1 Scaffold)

**Feature**: `001-backend-agent-scaffold` | **Date**: 2026-08-29

Phase 0 output. The major architecture is already locked in `DECISIONS.md`
(D1–D8); this file records the *implementation-level* decisions needed to build
it, each with rationale and alternatives considered. No NEEDS CLARIFICATION
items remain.

## R1 — OpenAI-compatible LLM client library

- **Decision**: Use `langchain-openai`'s `ChatOpenAI` pointed at the OpenCode
  gateway (`base_url` from env), wrapped by our factory.
- **Rationale**: D8 locks this wiring verbatim; `with_structured_output(
  PydanticModel)` gives us principle IV almost for free, and model swaps are
  env-only.
- **Alternatives considered**: raw `openai` SDK (we would hand-roll JSON schema
  prompting + parsing + retries — reinventing langchain-core); `langchain-
  community` (heavier, less maintained for this path).

## R2 — SSE serving mechanism

- **Decision**: Plain FastAPI `StreamingResponse` with `media_type=
  "text/event-stream"`; the route formats D7 frames manually
  (`event: <name>\ndata: <json>\n\n`).
- **Rationale**: D7 explicitly says "Plain FastAPI StreamingResponse, no
  websockets"; the event vocabulary is tiny (5 event types) so a dependency is
  unjustified (principle VIII).
- **Alternatives considered**: `sse-starlette` (nice ping/last-event-id support
  we don't need in MVP); websockets (rejected by D7).

## R3 — Graph construction, state, and streaming of lifecycle events

- **Decision**: One `StateGraph` with the fixed 7-node backbone and a single
  conditional edge out of `clarify_gate`; `MemorySaver` checkpointer;
  `thread_id` = client-supplied session id. Nodes emit D7 lifecycle events
  (status/message_delta/ui_update/error) through LangGraph's custom stream
  writer (`from langgraph.config import get_stream_writer`), consumed with
  `graph.astream(..., stream_mode="custom")` and translated 1:1 into SSE frames
  by the API layer.
- **Rationale**: Matches D6 exactly; the custom-writer path is the documented
  LangGraph mechanism for node-defined progress events, and it lets
  `respond` stream prose deltas as they are produced instead of buffering the
  whole answer. Verified against current LangGraph docs (streaming guide:
  `get_stream_writer` + `stream_mode="custom"`, `MemorySaver` via
  `config={"configurable": {"thread_id": ...}}`).
- **Alternatives considered**: returning events in state and emitting after
  completion (breaks incremental `message_delta` streaming); `astream_events`
  (event soup we would have to filter — more complexity, no benefit here);
  `SqliteSaver` (persistence is explicitly out of MVP scope per spec
  assumptions).

## R4 — Structured-output wrapper (validate → retry once → fail clean)

- **Decision**: A single helper `call_structured(llm, Model, messages)` in
  `app/llm/client.py`: invokes `llm.with_structured_output(Model)`, Pydantic-
  validates, and on `ValidationError` retries exactly once appending the
  validation error text to the conversation; a second failure raises a typed
  `StructuredOutputError` that the graph maps to one `error` protocol event.
- **Rationale**: Implements D8's resilience requirement in one audited place;
  every node shares it so fault-injection tests (SC-007) exercise one code
  path.
- **Alternatives considered**: per-node ad-hoc try/except (drift, untestable);
  json-repair libraries (masks model failure instead of surfacing it).

## R5 — Mock mode design

- **Decision**: `get_llm()` returns a `MockChatLLM` when `LLM_MODE=mock`
  (default when no key is configured). The mock implements the same surface the
  factory consumers use (invoke + `with_structured_output`) and returns
  deterministic canned outputs keyed by the requested Pydantic model type
  (intent extraction, preference weights, narration, plan selection), with
  knobs for tests (e.g. "always produce invalid output" for fault injection).
- **Rationale**: The whole pipeline and the entire test suite must run keyless
  and offline (FR-012, SC-006); determinism gives SC-001/SC-002.
- **Alternatives considered**: langchain's built-in fake chat models (not
  reliably structured-output-aware; we would still need model-type-keyed
  responses); recording/replaying real gateway traffic (network dependency in
  tests — forbidden).

## R6 — Scoring math (the pure function)

- **Decision**: `score_products(candidates, weights) -> list[ScoredProduct]`:
  1. LLM emits `PreferenceWeights` — one weight per scorable attribute
     (battery, comfort, anc, sound, value), each in `[0, 1]`, from priorities
     text. The LLM never sees or ranks products at this stage.
  2. The scorer normalizes weights to sum to 1 (all-zero → uniform).
  3. Each numeric attribute is min-max normalized **across the current
     candidate set** (cost attributes like `weight_g` and, outside the budget
     filter, `price_usd` are inverted); missing values score 0.5 (neutral).
  4. `score = Σ weight_i × normalized_attr_i`; categorical `anc_type` maps to
     an ordinal scale (none 0 → passive 0.33 → active 0.66 → adaptive/hybrid 1).
  5. Sort descending by score; ties broken by product id (lexicographic) so
     ordering is total and reproducible. Each `ScoredProduct` carries its
     per-attribute contributions (for narration grounding and tests).
- **Rationale**: Keeps the LLM out of ordering entirely (D3/principle III);
  min-max within candidates maximizes differentiation for the items the user
  will actually see; tie-break rule guarantees byte-identical output (FR-015).
- **Alternatives considered**: z-score normalization (unstable on 3-item
  candidate sets); raw-value scoring (dominated by scale differences);
  LLM-supplied order (forbidden by D3).

## R7 — Clarify gate rules (deterministic, pure)

- **Decision**: `clarify_gate(state) -> "ask" | "proceed"` is a pure function
  over extracted intent + session flags, with an exhaustive rule table:
  1. `category` missing or not present in catalog AND `asked_clarification`
     is false → **ask** (one question, chips = catalog categories + "Something
     else"); sets `asked_clarification`.
  2. Otherwise → **proceed**. Missing budget → apply category default cap
     (headphones: $250), record an assumption string. Priorities empty →
     default balanced weights. Requested attributes contradict budget (no
     product satisfies both) → proceed, set `flag_contradiction`.
- **Rationale**: D4 requires a deterministic check node, never an LLM
  judgment; the rule table is small enough to unit-test exhaustively.
- **Alternatives considered**: LLM-based "should I ask?" (forbidden); asking
  about budget (D4 explicitly says don't).

## R8 — Configuration and secrets

- **Decision**: `pydantic-settings` `Settings` reading `LLM_MODE` (default
  `mock`), `LLM_MODEL`, `OPENCODE_BASE_URL`, `OPENCODE_API_KEY`; `.env`
  supported, `.env.example` committed, real `.env` gitignored. Selecting
  `LLM_MODE=real` without a configured key/model raises at startup, not at
  first request.
- **Rationale**: Principle II (env-only, factory-only); fail-fast configuration
  beats lazy failure mid-conversation.
- **Alternatives considered**: plain `os.environ` reads scattered in modules
  (untestable, drifts); a config file (secrets-in-repo risk).

## R9 — Testing strategy without network or live server

- **Decision**: pytest with three layers: (a) pure unit tests (scorer, clarify
  rule table, DSL validation against fixture JSONs); (b) graph-level tests
  invoking `build_graph()` directly in mock mode, asserting on emitted custom
  events + final state; (c) API contract tests through `httpx.AsyncClient(
  transport=ASGITransport(app))` asserting the exact SSE frame sequence.
  Fault injection swaps the factory's LLM for a scripted fake.
- **Rationale**: No sockets, no credentials (SC-006); SSE contracts are
  asserted as byte-level frames, which is what the future frontend depends on.
- **Alternatives considered**: `TestClient` (buffering hides streaming order
  subtleties — httpx ASGI transport preserves the async generator semantics);
  spinning uvicorn in tests (slow, port-flaky on CI).

## R10 — Catalog authoring

- **Decision**: One JSON file `backend/app/catalog/data/headphones.json` with
  exactly 28 products across price tiers $49–$549; the flights scenario has
  four genuine winners with different tradeoff profiles: battery king
  (≥60 h), comfort king (lightest, top comfort score), ANC king (top anc
  score), value pick (best score-per-dollar under $200). Every product carries
  `review_scores` for comfort/anc/sound/battery/value plus 4–6 short quotes.
  Validated by the Pydantic `Product` model at load; loader fails loudly on a
  malformed catalog.
- **Rationale**: D5 requires exactly this shape; pre-scored reviews keep the
  research node free of runtime NLP (FR-005).
- **Alternatives considered**: SQLite (no query need at 28 items — principle
  VIII); multiple per-category files (only one category in MVP).

## R11 — Responses-API gateway models and the structured-output fallback

- **Decision**: Added `LLM_API_STYLE` (`auto` | `responses`) to the settings.
  When `responses`, the factory passes a responses-only parameter so langchain
  routes requests to `/responses` instead of `/chat/completions` — required
  for OpenCode Zen models like `muse-spark-1.2-contributor-free` that do not
  serve chat completions. Additionally, `call_structured` now degrades
  gracefully: it tries native `with_structured_output` first, and if the
  provider rejects the native structured-output contract at request time, it
  remembers the model and switches to schema-in-prompt JSON mode (schema JSON
  in the prompt, reply parsed and Pydantic-validated). Retry semantics are
  identical in both modes: exactly one validation-error retry, then a clean
  `StructuredOutputError`.
- **Rationale**: Verified against the live Zen gateway (2026-08-29): muse
  answers `/chat/completions` with HTTP 500 and rejects non-strict JSON
  schemas upstream; the Responses path with schema-in-prompt returns clean,
  schema-conforming JSON. The fallback keeps principle IV intact for any
  flaky free model instead of coupling the pipeline to one provider quirk.
- **Alternatives considered**: forcing strict JSON schemas for every model
  (upstream rejects open dicts like `priorities`); switching to the OpenAI
  Responses SDK wholesale (larger change, no benefit for other models);
  model-per-model capability config files (unnecessary — one env knob plus
  automatic fallback covers the observed matrix).

## R12 — Architecture review adjudication (post-Phase-1)

An independent review of the implemented backend (2026-08-29) returned
**sound-with-conditions**; this entry records the adjudicated decisions and
the accepted debt so they stop being tribal knowledge.

**Decisions (implemented in this pass):**

- **Plan selection is code-owned.** The `PlanSelection` model call was removed
  from `ui_plan_node`; component choice and title are deterministic constants
  in code. This is a conscious deviation from PRD §12's "UI Agent chooses the
  component": the LLM choice was never honored, and code-owned assembly is
  more reliable and one model call cheaper per turn. Revisit only when a
  component set exists that genuinely benefits from model selection.
- **`404 unknown_session` implemented** via an additive `ChatRequest.resume`
  flag (default `false`): a new session and a stale session are
  indistinguishable without a client signal, so `resume: true` + unknown
  session answers the contracted 404; `resume: false` always proceeds and
  registers the session. Guard order: 404 → 409 → stream.
- **CORS answered with middleware** (not a proxy-only contract amendment):
  `ALLOWED_ORIGINS` (comma-separated, defaulting to the Next.js dev ports),
  methods `GET, POST, OPTIONS`, headers `Content-Type, Authorization`,
  credentials off. Browsers can call the API directly in dev; proxying through
  Next.js server routes remains a valid client choice.
- **`LLM_MODE`/`LLM_API_STYLE` are validated** (case-insensitive; typos like
  `LLM_MODE=rel` now fail fast instead of silently running mock).
- **JSON-mode fallback trigger narrowed** to provider request-contract
  rejections (HTTP status 400/404/422 on the native call); transient errors
  (timeouts, 5xx) now propagate to the normal clean-error path instead of
  permanently downgrading the model's output enforcement.
- **`graph/followups.py` extracted** from `nodes.py` (pure resolver, zero
  behavior change) to keep the node module from accreating Phase 2 changes.

**Accepted debt (recorded, fix opportunistically):**

- Mock-mechanics sentinel blocks (`<<<CONTEXT>>>…`) travel inside production
  prompts, and the priority-alias table is duplicated between `llm/client.py`
  and `graph/nodes.py`.
- Real-mode determinism: FR-015 byte-identical rankings are a mock-mode
  guarantee; in real mode the scorer is deterministic *given* the weights, but
  weights come from a temp-0 model call that is not a hard cross-call
  contract.
- Client disconnect mid-turn does not cancel the in-flight graph run (benign
  single-user; burns LLM budget).
- The in-stream `busy`/`unknown_session` error codes are reserved vocabulary
  — unreachable by design (409/404 answer those cases pre-stream).
- The loader rejects a malformed catalog record outright rather than scoring
  partial products neutrally (spec edge case wording); for a curated shipped
  dataset the loud failure is the better behavior, and the scorer keeps a
  defensive neutral fill.
- Single-process constraint: sessions, live-session set, and busy guard are
  in-process state; multi-worker deployment requires a shared store (V2).
