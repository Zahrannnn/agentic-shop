# Feature Specification: Frontend UI Renderer & Chat (Phase 2)

**Feature Branch**: `002-frontend-ui-renderer`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Phase 2 frontend — the conversational shopping UI on the
owner-supplied Next.js boilerplate at `frontend/`: chat transcript with streamed agent
turns, a registry renderer for the agent's UI plan documents, the interactive shopping
loop (chips, compare, details, cart), the mirrored plan-contract validation with
fixture tests, and environment/health integration, per FRONTEND_GUIDE.md and the frozen
Phase 1 contracts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat turn lifecycle over the streaming contract (Priority: P1)

A shopper types a shopping request (e.g. "Help me find the best headphones for long
flights under $200") and sends it. The reply arrives as a live turn: a progress stepper
walks through the agent's stages in their fixed order, the answer text grows
incrementally in the transcript, and the turn ends with a clear completion. While any
turn is in flight the input is locked so a second message cannot interleave; when the
turn completes — successfully or with a visible error — input unlocks. The stream is
consumed directly from the chat endpoint even though the network may split the response
into arbitrary chunks mid-frame; the shopper never sees garbled or lost events because
of a chunk boundary.

**Why this priority**: The turn lifecycle is the load-bearing loop every other story
sits on — without a correctly parsed, correctly sequenced stream with lock/unlock
discipline, there is nothing to render and nothing to interact with.

**Independent Test**: With the backend in mock mode, send one complete request and
observe: stages appear in the contracted order, answer text accumulates in order, the
turn ends exactly once, and input is locked between send and completion. Feed the
parser a recording of the same stream split at hostile chunk boundaries (including
mid-frame) and confirm the parsed event sequence is identical.

**Acceptance Scenarios**:

1. **Given** a fresh conversation, **When** the shopper sends a complete request,
   **Then** the turn shows a stepper advancing through the lifecycle stages in their
   fixed order, the answer text appears incrementally, and the turn ends with a single
   explicit completion signal.
2. **Given** a turn is in flight, **When** the shopper tries to send another message,
   **Then** the input is disabled (or the send is visibly refused) until the current
   turn ends.
3. **Given** a turn that ends in failure, **When** the terminal error arrives,
   **Then** the error message is shown in the transcript, the input unlocks, and no
   completion signal is expected or awaited afterwards.
4. **Given** the same event stream delivered with chunk boundaries placed before,
   inside, and after frames (and a final frame missing its trailing blank line),
   **When** the stream is parsed, **Then** the event sequence is identical to the
   unsplit stream.

---

### User Story 2 - Plan renderer registry behind a validation gate (Priority: P1)

Every agent turn ends with one structured plan document describing what to show. The
frontend validates each plan against the mirrored plan contract before rendering and
then renders it with a fixed registry of exactly six components: a ranked product
grid, a preference picker with option chips, a side-by-side comparison table, a product
detail card, a cart summary, and a plain text/notice block. A new plan fully replaces
the previous turn's plan region; the transcript text and history persist. A plan that
fails validation is never rendered — the plan region shows a clear error state instead,
and the conversation continues.

**Why this priority**: The plan renderer is the product's central idea made visible —
"the UI is an output of the agent". It is co-P1 with the lifecycle because a rendered
recommendation is the first moment the product demonstrates its value.

**Independent Test**: Render each of the five published sample plan documents through
the validation gate and the registry — all five render correctly. Render mutated,
contract-violating plans (unknown component type, nonexistent product reference,
out-of-bounds lists, disallowed action) — none render; each shows the plan error state.

**Acceptance Scenarios**:

1. **Given** a recommendation turn's plan, **When** it arrives, **Then** the plan
   region renders a ranked grid of the referenced products with the allowed per-card
   actions, replacing the previous turn's plan region only.
2. **Given** a clarification turn's plan, **When** it arrives, **Then** the region
   renders the question's option chips exactly as listed, and the transcript answer
   text remains visible above it.
3. **Given** a plan that fails validation, **When** it arrives, **Then** nothing from
   that plan renders; the plan region shows an explicit error state and the transcript
   is unchanged.
4. **Given** two consecutive turns with different plan kinds, **When** the second plan
   arrives, **Then** the region shows only the second plan (full replace, no merging
   of the first).

---

### User Story 3 - Interactive shopping loop with session lifecycle (Priority: P2)

The shopper acts on what is rendered: tapping an option chip answers a clarifying
question; compare/details/add-to-cart buttons act on grid cards; a comparison table
offers a single "choose" action; the cart view offers item removal. Every tap sends the
plan's action object back to the agent unchanged and the next turn streams exactly like
a text turn. Free text is the other loop — positional phrases ("compare the first two")
are resolved by the agent, never by the frontend. The conversation keeps one stable
client-generated session identity across turns; after a page reload the next message
re-attaches if the backend still knows the session and transparently starts a fresh
session (with a small notice) if it does not.

**Why this priority**: It completes the MVP acceptance flow (search → clarify →
compare → inspect → cart) but depends on the lifecycle (US1) and renderer (US2)
existing first.

**Independent Test**: In one conversation in mock mode: get a recommendation, tap a
chip to answer a clarify question, request a comparison, open a product's details, add
to cart, remove from cart — every step happens inside the conversation, each turn
streaming and ending cleanly, with the session id constant throughout.

**Acceptance Scenarios**:

1. **Given** a rendered plan with actions, **When** the shopper taps one, **Then** the
   frontend sends exactly that action object to the agent with the conversation's
   session id and an empty message, and the reply streams as a normal turn.
2. **Given** the same conversation, **When** the shopper types free text referencing
   previous results ("compare the first two"), **Then** the reply reflects the agent's
   resolution of those references (the frontend resolves nothing itself).
3. **Given** a page reload mid-conversation, **When** the shopper sends the next
   message with re-attach intent, **Then** the conversation continues seamlessly if the
   backend still knows the session; if the backend restarted, a small expiry notice is
   shown and the conversation continues with a fresh session identity.
4. **Given** a turn already streaming, **When** a second request for the same session
   is somehow attempted, **Then** the busy conflict is surfaced as a disabled input
   with a retry affordance, never as a crashed or duplicated turn.

---

### User Story 4 - Mirrored plan contract proven by fixture tests (Priority: P2)

The frontend owns a validation mirror of the published plan contract. The contract test
suite reads the backend's five sample plan documents directly — the same files that pin
the backend — and proves the frontend accepts every one of them, plus proves it rejects
each known-bad mutation class: unknown component type, product reference that does not
exist in the catalog, arrays outside their contracted bounds, and an action type not
allowed for its component. This keeps both sides honest whenever either changes: if
backend and frontend drift apart, a test goes red on the next run.

**Why this priority**: This is the D8 double-sided contract obligation and the safety
net for US2's gate, but it is a developer-facing guarantee that delivers no shopper
value by itself; it must exist before the renderer can be trusted, which is why it is
built during foundation rather than last.

**Independent Test**: Run the frontend contract test suite with no backend running:
five fixture documents pass validation; each known-bad mutation (unknown type, foreign
product id, out-of-bounds list, disallowed action) fails validation with a precise
reason.

**Acceptance Scenarios**:

1. **Given** the five published sample plan documents, **When** each is parsed through
   the frontend's plan schema, **Then** all five validate and yield typed render
   models.
2. **Given** a fixture mutated to use an unknown component type, **When** it is
   parsed, **Then** validation rejects it with an unknown-type reason.
3. **Given** a fixture mutated to reference a product id absent from the catalog,
   **When** it is parsed, **Then** validation rejects it with a foreign-reference
   reason.
4. **Given** fixtures mutated past their contracted collection bounds or given an
   action type not allowed for their component, **When** parsed, **Then** validation
   rejects each with the corresponding reason.

---

### User Story 5 - Environment integration, long-latency tolerance & polish (Priority: P3)

The shop is reachable without any login. The backend location comes from validated
public environment configuration (no hard-coded URLs), and the app surfaces which
backend mode it is talking to (deterministic mock vs. real model) via a small health
badge fed by the backend's health endpoint. In real mode a turn can take tens of
seconds: the stepper keeps showing honest progress through long quiet gaps and the app
never gives up mid-turn on a client-side timeout. Empty and failure states are
designed, not accidental: an empty option list, a failed plan, an unreachable backend
each render a deliberate state. The interface meets accessibility basics — labeled
controls, visible focus, keyboard-operable actions, semantic regions, reduced-motion
respect.

**Why this priority**: Essential for daily real use and demos, but the product works
without it in mock mode; it is the finishing layer over the functioning loop.

**Independent Test**: Point the app at a health endpoint reporting mock mode → the
badge says mock; report real → badge says real. Simulate a turn with long silent gaps
between stages → the stepper stays honest and the turn completes when the stream does.
Unplug the backend → the app shows a deliberate connectivity error, not a blank screen.

**Acceptance Scenarios**:

1. **Given** the backend's health endpoint reporting a mode, **When** the app loads,
   **Then** a visible badge shows that mode and updates on refresh.
2. **Given** real-mode latency (tens of seconds with quiet gaps), **When** a turn is
   in flight, **Then** progress remains visible, no client timeout interrupts the
   turn, and input stays locked until the terminal frame.
3. **Given** a plan component rendered from data with an empty list (e.g. zero
   options), **When** it renders, **Then** the UI shows a designed empty state instead
   of a blank region.
4. **Given** a keyboard-only shopper, **When** they tab through the transcript, plan
   actions and the message input, **Then** every control is reachable, focus is
   visible, and actions are operable without a pointer.

---

### Edge Cases

- What happens when the network splits a stream frame across chunks (e.g. blank-line
  separator in one chunk, JSON line in the next)? → The parser accumulates and splits
  on frame boundaries, so the event sequence is unaffected; a final frame without its
  trailing blank line (stream cut) still parses.
- What happens when the backend restarts mid-conversation? → The next message sent
  with re-attach intent gets a not-found answer; the frontend shows a small "session
  expired — starting fresh" notice, generates a new session id, and resends without
  re-attach intent.
- What happens when a second request races a streaming turn (e.g. a second browser
  tab on the same session)? → The busy conflict answer is surfaced as a disabled input
  with a retry affordance; the in-flight turn owns the session and finishes normally.
- What happens when a plan arrives with an unknown component type despite the
  contract? → The validation gate rejects it before render; the plan region shows the
  error state. There is no fallback rendering of unknown types (that is the contract,
  deliberately non-forward-compatible).
- What happens when a picker arrives with zero options, or a grid with an empty
  product list? → Within bounds it cannot (the contract forbids it); if it does, the
  validation gate rejects it; where an empty list is within bounds (e.g. an empty
  cart view), a designed empty state renders.
- What happens when the stream ends with no terminal frame at all (connection
  dropped)? → The turn is marked failed after the stream closes without a terminator;
  the input unlocks with an error state and the last valid plan stays visible.
- What happens when a malformed data line (unparsable JSON) arrives? → The frame is
  ignored as a protocol violation and the turn continues; the transcript notes the
  anomaly rather than crashing.
- What happens when the shopper reloads mid-turn? → The turn is lost (no persistence
  in MVP); after reload the resume flow applies — the backend either continues the
  session or answers not-found and a fresh session starts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let the shopper send a free-text message and present the
  agent's reply as one streamed turn with a progress stepper, incrementally appended
  answer text, one rendered plan region, and exactly one terminal outcome
  (completion or visible error).
- **FR-002**: The system MUST consume the chat stream over the frozen POST +
  server-sent-events contract and MUST parse frames by accumulating the response body
  and splitting on frame boundaries, tolerating arbitrary network chunk splits, frames
  missing the trailing blank line at stream end, and ignoring unparsable data lines.
- **FR-003**: The system MUST reflect every progress stage in the stepper in the
  contracted order, MUST NOT require any particular stage to appear (clarification
  turns stop after the first stage), and MUST treat the stage carrying a count as
  informational.
- **FR-004**: The system MUST append answer text increments in arrival order to the
  current turn's answer bubble and MUST NOT render, alter, or clear the plan region
  from text increments.
- **FR-005**: The system MUST treat the first terminal frame as final: on success the
  input unlocks; on error the message is displayed, the input unlocks, and the last
  valid plan remains visible. If the stream closes with no terminal frame, the turn
  MUST end in a visible failed state and unlock.
- **FR-006**: The system MUST validate every received plan against the mirrored plan
  schema before any rendering; an invalid plan MUST render only the plan-region error
  state — never partially rendered content — and MUST NOT disturb the transcript.
- **FR-007**: The system MUST render plans through a fixed registry of exactly six
  component kinds — product grid, preference picker, comparison table, product
  details, cart view, text block — each honoring its contracted props, bounds, and
  allowed actions.
- **FR-008**: The system MUST fully replace the plan region on each new plan (no
  diffing or merging, per the full-replace contract) while preserving transcript text
  and history across turns.
- **FR-009**: The system MUST send plan interactions by POSTing the tapped action
  object verbatim (type, label, payload) with the conversation's session id and an
  empty message; free text MUST be sent as the message; all six contracted action
  kinds (answer preference, compare, details, add to cart, remove from cart, choose)
  MUST be wired to their rendered controls.
- **FR-010**: The system MUST generate a session identity per conversation (8–64
  characters), keep it stable across the conversation, re-attach after page reload by
  sending the next message with resume intent, and on a not-found answer MUST show an
  expiry notice, generate a fresh identity, and resend without resume intent. A
  brand-new conversation MUST never send resume intent.
- **FR-011**: The system MUST keep one turn in flight per conversation: lock input on
  send, unlock on the terminal frame, and surface a busy-conflict response as a
  disabled input with a retry affordance rather than an error crash.
- **FR-012**: The system MUST mirror the published plan contract as validation schemas
  and MUST ship contract tests that read the backend's five sample plan documents as
  the single source of truth and prove: all five validate; unknown component types,
  catalog-foreign product references, out-of-bounds collections, and disallowed action
  types are rejected.
- **FR-013**: The system MUST make the shopping experience reachable without
  authentication, MUST take the backend base URL from validated public environment
  configuration, and MUST display the backend's reported mode (mock/real) as a health
  badge fed by the health endpoint.

### Key Entities *(include if feature involves data)*

- **UiPlan**: One turn's complete interface description received from the agent —
  plan version, session and turn identifiers, and exactly one root component.
  Stands alone: never needs the previous plan to render.
- **PlanComponent**: The root's single component — its kind (one of the six registry
  kinds), its properties (titles, product references, options, attributes, cart items,
  text), and its allowed actions. Bounded per kind by the contract.
- **PlanAction**: One shopper interaction offered by a component — a kind, a display
  label, and a payload. Sent back to the agent verbatim when tapped.
- **Turn**: One request/response round trip in the transcript — the shopper's text or
  action, the lifecycle stages seen so far, the accumulated answer text, the rendered
  plan (or none), and the terminal outcome (completed, failed, or in flight).
- **Session**: One conversation — its client-generated identity and whether the
  backend currently knows it (live or expired). Drives the resume/fresh-start flow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of mock-mode turns, lifecycle stages appear in the contracted
  order, answer text accumulates in order, and exactly one terminal outcome occurs —
  verified by automated tests replaying recorded streams.
- **SC-002**: Streams replayed with chunk boundaries placed before, inside, and after
  every frame (plus a truncated final frame) produce parsed event sequences 100%
  identical to the unsplit stream.
- **SC-003**: 100% of the five published sample plan documents pass the validation
  gate and render through the registry; 100% of the four known-bad mutation classes
  are rejected before render.
- **SC-004**: The full MVP flow — recommendation → clarify answer → compare →
  details → add to cart → remove — completes inside one conversation with zero
  navigations away from it and zero manual state recovery.
- **SC-005**: In 100% of in-flight turns the input is locked from send to terminal
  frame; a normal UI user never triggers a busy conflict, and an induced conflict
  renders the retry affordance 100% of the time.
- **SC-006**: With the backend unreachable, the full frontend automated check suite
  (lint, types, unit/contract tests, production build) still passes — no test
  requires a live backend; the joint smoke test with a live mock-mode backend then
  completes the MVP flow end to end.
- **SC-007**: Every induced mid-turn failure (error frame, connection drop, invalid
  plan) leaves the last valid plan visible, surfaces a human-readable message, and
  unlocks input — verified across all induced failure cases with zero crashes and
  zero partially rendered plans.

## Assumptions

- The backend runs locally (default `http://127.0.0.1:8000` in development); its
  location is environment configuration, not code. The backend's CORS defaults already
  cover the frontend's dev origin; a proxy through the frontend's own server routes
  remains an allowed alternative if deployment requires it.
- Sessions are in-memory server-side: a backend restart expires them by design; the
  resume-then-fresh-start flow is the accepted recovery (matching the Phase 1
  contract), not a persistence feature.
- The plan contract is frozen at the Phase 1 documents (`http-api.md`, `ui-dsl.md`)
  and their shared fixture corpus; any drift is a backend-contract change, not
  something the frontend patches around. The fixture corpus lives in the same
  repository (`backend/fixtures/ui-plans/`), and the frontend's contract tests read
  those files directly — the monorepo layout is a stated dependency of that mechanism.
- Development and CI run against mock mode (deterministic, sub-second turns, no
  credentials); real-mode latency behavior (tens of seconds) is covered by design
  requirements and manual verification, not automated timing tests.
- The cart is a mock (contents and totals only); no payments, checkout, or real
  inventory exists anywhere in the system.
- Single shopper, single browser tab is the normal case; a second concurrent tab on
  the same session is handled gracefully (busy conflict) but is not an optimized flow.
- Streaming transport details (POST + streamed response, frame format, event
  vocabulary) are named in this spec only because they are frozen interface contracts
  from Phase 1, not implementation choices of this phase.
