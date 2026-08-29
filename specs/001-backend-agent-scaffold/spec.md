# Feature Specification: Agentic Shopping Backend (Phase 1 Scaffold)

**Feature Branch**: `001-backend-agent-scaffold`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Phase 1 backend scaffold — the conversational shopping
agent backend: catalog, shopping tools, agent workflow, UI plan documents, and a
streaming chat API, per the target layout in AGENTS.md and the locked decisions in
DECISIONS.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete shopping request end-to-end (Priority: P1)

A shopper sends one natural-language message containing a complete request, e.g.
"Help me find the best headphones for long flights under $200. Noise cancellation
and comfort matter most." The system understands the request (category, budget,
use case, priorities), finds matching products in the catalog, researches the
strongest candidates, computes a ranking, and streams back a short conversational
answer that recommends the top three products — each with a plain-language reason
grounded in the products' actual attributes (e.g. "40h battery — the longest in
your budget"). While working, the system streams progress updates (understanding
→ searching → found N → researching → ranking → building results) so the shopper
sees it is working, and the turn ends cleanly.

**Why this priority**: This is the product's core value claim — one sentence in, a
trustworthy explained recommendation out — and every other story is a variation of
this pipeline.

**Independent Test**: Send one complete shopping request to a fresh session and
observe: an ordered progress sequence, a conversational answer naming exactly
three ranked products with attribute-grounded reasons, and a clean end-of-turn
signal. No follow-up input required.

**Acceptance Scenarios**:

1. **Given** a fresh session, **When** the shopper sends a complete request
   (category + budget + priorities), **Then** the reply names exactly the top three
   ranked products, each with at least one reason citing a real attribute value,
   and the highest-ranked product is the one the deterministic score ranks first.
2. **Given** the same request, **When** the pipeline runs, **Then** progress
   updates arrive before the final answer in the fixed lifecycle order, and the
   turn ends with an explicit end-of-turn signal.
3. **Given** a request whose budget excludes some catalog items, **When** the
   pipeline ranks, **Then** no product above the stated budget appears in the
   recommendation.

---

### User Story 2 - Clarifying an incomplete request (Priority: P2)

A shopper sends a request that lacks the shopping category or names one the
catalog does not carry ("Help me pick a gift"). The system asks exactly one
clarifying question, offering tappable option chips (e.g. Headphones / Laptops /
Something else) in place of a free-text requirement, and ends its turn. When the
shopper answers — by chip or by sentence — the system runs the request to
completion without asking anything further. Two special cases run without asking:
a missing budget proceeds using a sensible cap for the category while openly
stating the assumption; contradictory constraints ("under $50, best noise
cancellation") proceed with the closest matches and honestly flag the trade-off.

**Why this priority**: It makes the agent feel competent on imperfect input, which
is how real users actually talk, and it is the single conditional branch in the
workflow.

**Independent Test**: Send a category-less request → receive exactly one question
with option chips and an end-of-turn signal; reply with a category → receive the
full User Story 1 outcome with no second question.

**Acceptance Scenarios**:

1. **Given** a request with no recognizable category, **When** it is submitted,
   **Then** the reply is exactly one question with option chips, and the turn ends.
2. **Given** the shopper answered the clarifying question, **When** the pipeline
   resumes, **Then** it completes to a recommendation without asking again.
3. **Given** a request with a budget and no priorities, **When** the pipeline runs,
   **Then** it completes without asking, applying a stated budget assumption.
4. **Given** contradictory constraints, **When** the pipeline runs, **Then** the
   reply presents the closest matches and explicitly says the ideal combination
   does not exist in the catalog.

---

### User Story 3 - Every turn carries a renderable UI plan (Priority: P2)

Every completed agent turn — answer, clarification, comparison, cart change —
ends with exactly one structured UI plan document describing what the interface
should show (e.g. a results grid, a preference picker with chips, a comparison
table, a cart confirmation). The plan is a data document, never executable code,
and it fully replaces the previous turn's plan. A client that knows only the
published plan schema can render it without understanding the agent, and an
invalid plan is rejected before it ever reaches the client.

**Why this priority**: The UI plan is the contract that makes the frontend phase
possible and is the project's central architectural idea ("the UI is an output of
the agent").

**Independent Test**: For each request type in this feature (complete request,
clarification, comparison, cart change), capture the final plan emitted for the
turn and validate it against the published schema — all must pass, and each must
be a complete document, not a delta.

**Acceptance Scenarios**:

1. **Given** any completed turn, **When** the client receives the turn's plan,
   **Then** it validates against the published plan schema with no unknown
   component types.
2. **Given** a second turn in the same session, **When** its plan arrives,
   **Then** it is a full standalone document that renders correctly with no
   reference to the previous plan.
3. **Given** a generated plan containing an invalid structure, **When** the
   pipeline finishes the turn, **Then** the client receives a clean error event
   and never the invalid plan.

---

### User Story 4 - Multi-turn follow-ups in one session (Priority: P3)

Within the same conversation the shopper refines and acts: "only show ones with
more than 30 hours battery", "compare the first two", "tell me more about the
second one", "I care more about comfort than sound quality", "add that one to my
cart". The system remembers the conversation and the current candidate set, so
phrases like "the first two" and "that one" resolve correctly; comparison turns
produce a side-by-side plan of the requested products; preference changes
re-rank and re-present the results; cart turns add/remove items and confirm the
cart contents. All of this happens in the transcript — the shopper never leaves
the conversation.

**Why this priority**: It completes the MVP acceptance flow (search → refine →
inspect → compare → recommend → cart) but depends on the recommendation turn
existing first.

**Independent Test**: In one session: get a recommendation, then issue a compare
command referencing positional products, a preference re-rank, and an add-to-cart;
verify each reply resolves the references from session context and the final cart
contents are exactly the items added.

**Acceptance Scenarios**:

1. **Given** a session with a ranked result set, **When** the shopper says
   "compare the first two", **Then** the reply's plan is a comparison of exactly
   the first- and second-ranked products from the previous turn.
2. **Given** the same session, **When** the shopper states a changed priority,
   **Then** the products are re-scored with the new weights and may legitimately
   reorder; the reply explains what changed.
3. **Given** the same session, **When** the shopper adds a referenced product to
   the cart, **Then** the cart for that session contains that product and the
   reply confirms it with a cart plan; a later remove reverses it.

---

### User Story 5 - Keyless, deterministic, fail-clean operation (Priority: P2)

An operator (developer, CI, or demo) runs the entire pipeline with no AI service
credentials: a built-in mock mode emulates every model call so all five user
stories work offline, deterministically. When a real model is configured and
returns output that fails validation, the system retries once with the validation
error fed back, then emits a clean, human-readable error event — never raw model
output or a crash. Identical requests to identical fresh sessions always produce
identical rankings; nothing in scoring depends on time, randomness, or network
order.

**Why this priority**: Every automated check in this project must run without
credentials, and determinism is the product's trust anchor; but it delivers value
through the other stories.

**Independent Test**: With no credentials configured, run the full quality-check
suite and one full shopping conversation — both succeed. Run the same complete
request in two fresh sessions — the rankings are identical. Point the model at an
endpoint returning malformed output — the client receives exactly one retry
followed by one clean error event.

**Acceptance Scenarios**:

1. **Given** no AI credentials in the environment, **When** the full automated
   test suite runs, **Then** every check passes without network access.
2. **Given** the same complete request sent to two fresh sessions in mock mode,
   **When** both turns complete, **Then** the ranked product lists are identical
   item-for-item and order-for-order.
3. **Given** a model endpoint that returns structurally invalid output, **When** a
   turn runs, **Then** exactly one retry occurs with the validation error fed
   back, and a second failure produces a single clean error event that ends the
   turn.

---

### Edge Cases

- What happens when the shopper names a category the catalog does not carry?
  → Treated as "category unknown": one clarifying question with chips (US2).
- What happens when filtering leaves zero products? → The system relaxes the
  least-important constraint, states what it relaxed, and presents the closest
  matches instead of an empty screen.
- What happens when the shopper sends a new message while the previous turn is
  still processing in the same session? → The turn in flight owns the session; a
  second simultaneous message for the same session is refused with a clear
  busy signal rather than interleaving two answers.
- What happens when the process restarts mid-conversation? → Sessions are
  in-memory by design; the client is told the session no longer exists and must
  start a new one. Acceptable for MVP.
- What happens when a catalog product has missing attributes or no review
  scores? → Missing values score as neutral; the pipeline never crashes on a
  partial product record.
- What happens when the model output passes validation but references product
  IDs that do not exist in the catalog? → Those references are dropped and the
  plan/answer is built only from catalog-verified products.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a conversational chat endpoint that accepts a
  natural-language message for a session and streams the agent's turn back as an
  ordered event stream (progress status events, answer text increments, one UI
  plan document, an end-of-turn event, or an error event).
- **FR-002**: The system MUST extract shopping intent from each message: category,
  budget, use case, and stated priorities, merged with any intent already known
  in the session.
- **FR-003**: The system MUST apply a deterministic, rule-based clarify gate —
  not a model judgment: unknown/missing category → exactly one question with
  option chips; missing budget → proceed with a sensible category cap and state
  the assumption; contradictory constraints → proceed with closest matches and
  flag them. The gate MUST never ask twice in a row, and after any answer MUST
  run to completion.
- **FR-004**: The system MUST search a curated catalog of approximately 28
  headphone products by category, price ceiling, and stated attributes, returning
  matching candidates.
- **FR-005**: The system MUST research candidates using per-attribute pre-scored
  review summaries and short quotes stored with each product; it MUST NOT perform
  natural-language extraction over review text at runtime.
- **FR-006**: The system MUST translate the shopper's priorities into attribute
  weights via a model call, then MUST compute the ranking with a pure,
  side-effect-free scoring function (weighted sum of normalized attributes);
  the model MUST never determine the order.
- **FR-007**: The system MUST narrate the top three products with reasons that
  reference the computed attribute values of those specific products.
- **FR-008**: Every completed turn MUST end with exactly one UI plan document
  that validates against the published plan schema and fully replaces the
  previous turn's plan; the plan MUST describe components from the MVP registry
  set (results grid, preference picker with chips, comparison table, product
  details, cart view, status/error views) — never executable code.
- **FR-009**: The event stream MUST follow the fixed lifecycle: progress status
  events in stage order, answer text increments, one validated plan document,
  then end-of-turn; on failure, a single error event ends the turn.
- **FR-010**: The system MUST support in-conversation follow-ups: refine
  constraints, compare referenced products, inspect product details, change
  priorities, and add/remove/list mock cart items, resolving positional and
  demonstrative references ("the first two", "that one") from session context.
- **FR-011**: The system MUST maintain per-session state (conversation, current
  intent, candidates, ranking, current plan, cart) across turns within a session,
  isolated between concurrent sessions.
- **FR-012**: The system MUST provide a mock mode that emulates every model call
  deterministically so the entire pipeline, including the automated test suite,
  runs with no credentials and no network.
- **FR-013**: Every model call MUST request schema-validated structured output;
  on validation failure the system MUST retry exactly once feeding the validation
  error back, and on second failure MUST end the turn with a single clean error
  event.
- **FR-014**: The system MUST expose a health check endpoint for liveness probes.
- **FR-015**: The system MUST run all model calls at temperature 0 and produce
  byte-identical rankings for identical inputs to identical fresh sessions.
- **FR-016**: The system MUST refuse a new message for a session while a turn for
  that session is still in flight (clear busy signal; other sessions unaffected).

### Key Entities *(include if feature involves data)*

- **Product**: A catalog item — identity, name, price, and measurable attributes
  (e.g. battery life, weight, noise-cancellation type, driver size, supported
  codecs, multipoint, folding), plus per-attribute pre-scored review ratings and
  4–6 short review quotes.
- **UserIntent**: What the shopper wants — category, budget ceiling, use case,
  named priorities; accumulated across turns in a session.
- **Session**: One conversation — its message history, accumulated intent,
  current candidates, current ranking, current plan, cart, and whether a turn is
  in flight. Identified by a session id supplied by the client.
- **ScoredRecommendation**: One ranked product with its computed score and the
  attribute-grounded reasons for its position.
- **UIPlan**: One turn's full interface description — a tree of registry
  components (type + props + allowed actions) that validates against the
  published schema.
- **UIAction**: A shopper interaction with the rendered plan (compare, select
  preference, add to cart, …) delivered back to the agent as part of a follow-up
  message.
- **CartItem**: A product added to a session's mock cart, with quantity.
- **ProtocolEvent**: One unit of the streamed turn — progress status, answer text
  increment, UI plan, end-of-turn, or error — with a defined stage order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete shopping request in mock mode produces its full turn —
  lifecycle events, answer, and validated plan — in under 5 seconds with no
  network access.
- **SC-002**: The same complete request sent to two fresh sessions produces
  100% identical ranked product lists (item and order), verified across at least
  3 repeated runs.
- **SC-003**: Across all clarification scenarios, the system asks at most one
  question per request, and 100% of answered requests then complete to a
  recommendation with zero further questions.
- **SC-004**: 100% of plans emitted across a 50-scenario automated run (all
  request types) validate against the published plan schema.
- **SC-005**: A shopper can complete search → refine → inspect → compare →
  recommendation → add-to-cart entirely inside one session, with zero
  navigations outside the conversation.
- **SC-006**: The full automated quality-check suite passes on a machine with no
  AI credentials configured and no network access.
- **SC-007**: A malformed model response results in exactly one retry and, if
  still invalid, exactly one clean error event — verified by fault-injection
  tests with 0 raw model outputs leaking to the client.

## Assumptions

- Single-user local/development deployment; no authentication or multi-tenancy
  in MVP.
- Shopping requests arrive in English.
- Session state is in-memory and intentionally lost on process restart; clients
  are expected to start a new session after a restart. No database in MVP.
- The catalog is a fixed, curated dataset shipped with the backend (~28
  headphones, one scenario-rich set with 4 genuine "flights" winners: battery
  king, comfort king, ANC king, value pick); no ingestion pipeline.
- The cart is a mock: totals and contents only, no payment or checkout.
- The streaming chat endpoint is the locked server-sent-events contract defined
  in DECISIONS.md D7; any SSE-capable client (including command-line tools) can
  act as the frontend for testing.
- The exact AI model is an environment-configured choice behind the OpenCode
  gateway; the backend MUST work with any compliant model, and the wrapper
  behavior of FR-013 covers model variance.
- UI plan validation relies on a shared fixture corpus (`fixtures/ui-plans/`)
  as the single source of truth for the plan contract, reused later by the
  frontend phase.
