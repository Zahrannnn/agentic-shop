# Data Model — Frontend UI Renderer & Chat (Phase 2)

**Feature**: `002-frontend-ui-renderer` | **Date**: 2026-08-29

Everything here is client-side TypeScript in `frontend/src/features/shopping/`. The
wire side (camelCase plan envelope, SSE frames) is consumed verbatim from
[`specs/001-backend-agent-scaffold/contracts/`](../001-backend-agent-scaffold/contracts/ui-dsl.md);
this file defines the Zod mirror, the Redux Toolkit state, the hook contracts, and
the parser I/O types. Zod schemas live in `validations/`, slices in `store/`,
parser in `api/`, per plan.md's project structure.

## Zod schema set (`validations/ui-plan-schema.ts`)

Mirrors `contracts/ui-dsl.md` rule-for-rule. All field names are the camelCase wire
names (the backend emits camelCase; there is no rename layer).

### `uiActionSchema` → exported type `UIAction`

| Field | Schema | Rules |
|---|---|---|
| `type` | `z.enum(["compare", "details", "select_preference", "add_to_cart", "remove_from_cart", "choose"])` | full action vocabulary |
| `label` | `z.string().min(1)` | non-empty display label |
| `payload` | `z.record(z.string(), z.unknown())` | object, possibly empty; shape refined per component below |

### Component prop schemas (discriminated union `planComponentSchema` on `type`)

| Discriminator | Props schema | Bounds / refinements | Allowed actions |
|---|---|---|---|
| `product_grid` | `title: string (min 1)`, `productIds: z.array(catalogId).min(1).max(6)`, `ranked: boolean` | every id ∈ catalog set | `compare`, `details`, `add_to_cart` |
| `preference_picker` | `question: string (min 1)`, `options: z.array(z.string().min(1)).min(2).max(4)` | every option has a matching `select_preference` action whose `label === option` (super-refine) | `select_preference` only |
| `comparison_table` | `productIds: z.array(catalogId).min(2).max(3)`, `attributes: z.array(z.string().min(1)).min(1)` | at most one `choose` action (super-refine); `choose` payload has `productId` ∈ `productIds` | `choose` only |
| `product_details` | `productId: catalogId`, `showQuotes: boolean` | — | none (`actions` must be empty) |
| `cart_view` | `items: z.array(z.object({ productId: catalogId, quantity: z.number().int().min(1).max(10) })).min(1)`, `totalUsd: z.number().nonnegative()` | each `remove_from_cart` payload `productId` ∈ items | `remove_from_cart` only |
| `text_block` | `heading: string optional`, `body: string (min 1)` | — | none |

`catalogId` is `z.string().min(1).refine(id => CATALOG_PRODUCT_IDS.has(id))` where
`CATALOG_PRODUCT_IDS` comes from `utils/catalog-refs.ts` (see below).

### `uiPlanSchema` → exported type `UiPlan`

| Field | Schema | Rules |
|---|---|---|
| `planVersion` | `z.literal("1")` | contract rule 1: exactly `"1"` |
| `sessionId` | `z.string().min(1)` | non-empty echo of the session |
| `turnId` | `z.number().int().min(1)` | per-turn identity |
| `root` | `planComponentSchema` | exactly one root component |

Exported TS types: `UiPlan`, `UIAction`, `PlanComponent` (union), plus per-component
aliases (`ProductGridProps`, `PreferencePickerProps`, `ComparisonTableProps`,
`ProductDetailsProps`, `CartViewProps`, `TextBlockProps`) derived with `z.infer` —
no hand-written duplicate types.

### Validation rules mirrored (each traces to `contracts/ui-dsl.md` §Validation rules)

1. Envelope literal + non-empty session + integer turn ≥ 1 → rule 1.
2. Discriminated union on `root.type`; unknown type fails with `invalid_literal`
   (no fallback branch exists to hit) → rule 2.
3. Catalog-membership refinement on every `productId` → rule 3.
4. Per-type allowed-action sets; labels `min(1)`; payload refinements above → rule 4.
5. Collection bounds in the array schemas → rule 5.
6. Schemas validate data only; no code execution path exists → rule 6 (trivially).

### `utils/catalog-refs.ts`

Exports `CATALOG_PRODUCT_IDS: ReadonlySet<string>`, the mirror of the backend
catalog's ids, kept as a literal constant for bundle-ability. The contract test
cross-checks it against `backend/app/catalog/data/headphones.json` (fs-read) so any
backend catalog change fails the frontend suite until the constant is regenerated.

### Fixture loader (`validations/fixtures.ts`, test-only)

`loadUiPlanFixtures(): Record<FixtureName, UiPlan>` — resolves
`../../../../backend/fixtures/ui-plans/` relative to the module (**monorepo-root
assumption**: `frontend/` and `backend/` are siblings in one checkout), reads the five
JSON files with `node:fs`, and returns raw JSON for the tests to run through
`uiPlanSchema`. Not imported by any runtime module.

## Protocol-side schemas (lightweight, `api/`)

SSE frames are parsed positionally (parser, below), not schema-parsed; only the two
data payloads with structure worth guarding get schemas in the same file style:

- `statusDataSchema`: `{ stage: z.enum(["intent_parsed","searching","found_n","researching","ranking","building_ui"]), count?: z.number().int().positive() }`
- `errorDataSchema`: `{ message: z.string().min(1), code: z.enum(["structured_output","busy","unknown_session","internal"]).optional() }`
- `messageDeltaDataSchema`: `{ text: z.string() }`; `turn_end` data is `{}`.
- `ChatRequestBody` (TS type, not Zod — it is our own outgoing payload):
  `{ session_id: string; message: string; ui_action: UIAction | null; resume: boolean }`
  (snake_case per the contract's request-body exception).

## Redux Toolkit state (`store/`)

Registered in `src/shared/store/store.ts` as `agentSession` and `agentTranscript`
next to the existing `preferences` slice. Typed hooks follow the boilerplate's
`RootState`/`AppDispatch` exports.

### `sessionSlice` → state `SessionState`

| Field | Type | Notes |
|---|---|---|
| `sessionId` | `string` | client-generated per conversation (`crypto.randomUUID()`, 36 chars — within the 8–64 contract) |
| `live` | `boolean` | whether the backend is known to still hold the session; starts `true`, flips `false` on a 404 |

Actions: `sessionStarted({ sessionId })`, `sessionExpired()` (sets `live: false`;
the resume flow then generates a new id via `sessionStarted`).

**Persistence**: the slice persists `sessionId` + `live` (and the transcript slice
its `turns`) to `window.sessionStorage` under a single namespaced key, rehydrating
at store creation. This is what makes the resume flow real: a page reload keeps the
conversation identity so the next message can be sent with `resume: true` (US3
scenario 3) and the transcript stays visible. `sessionStorage` (not `localStorage`)
keeps conversations tab-scoped, matching the single-conversation-per-tab MVP; no
cross-restart durability is claimed or needed (sessions are server-side in-memory by
design).

### `transcriptSlice` → state `TranscriptState`

`turns: Turn[]` (append-only) plus `activeTurnId: string | null` and derived
`isStreaming` (= an active turn exists without a terminal outcome; input lock reads
this).

**Turn** (one element of `turns`):

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | client-generated turn identity (uuid) |
| `userText` | `string` | free text sent (empty string for action turns) |
| `userAction` | `UIAction \| null` | action object sent verbatim, if the turn was an action tap |
| `stagesSeen` | `LifecycleStage[]` | ordered subset of the six stages received so far (drives the stepper) |
| `foundCount` | `number \| null` | count from the `found_n` stage, when seen |
| `answerText` | `string` | all `message_delta` text joined in arrival order |
| `plan` | `UiPlan \| null` | last validated plan for this turn (`null` until `ui_update`; invalid plans never enter state) |
| `planError` | `string \| null` | validation failure reason, when the gate rejected a plan |
| `state` | `"streaming" \| "rendering" \| "done"` | local lifecycle: streaming (post-send, pre-plan), rendering (plan received, awaiting terminal), done (terminal reached or stream closed) |
| `terminal` | `"turn_end" \| "error" \| null` | which terminator closed the turn; `null` while in flight |
| `errorMessage` | `string \| null` | display message from the `error` frame |
| `errorCode` | `string \| null` | contracted error code, when present |

Actions dispatched by the turn pipeline (`hooks/use-agent-turn.ts`):

- `turnStarted({ id, userText, userAction })` — locks input, resets stepper
- `turnStatus({ id, stage, count? })` — appends stage (idempotent per stage)
- `turnDelta({ id, text })` — appends answer text
- `turnPlanAccepted({ id, plan })` — stores the validated plan; `state → "rendering"`
- `turnPlanRejected({ id, reason })` — sets `planError` (render error state); stream
  continues to its terminator
- `turnCompleted({ id })` / `turnFailed({ id, message, code })` — set `terminal`,
  `state → "done"`, unlock input
- `turnDropped({ id, message })` — stream closed with no terminal frame (network
  drop): same unlock path as failure, distinct message
- `busyRejected({ id })` — 409 before streaming: turn marked failed with the retry
  affordance message; input unlocks

Selectors: `selectIsStreaming`, `selectActiveTurn`, `selectTurns`,
`selectCurrentPlan` (last accepted plan across turns — for the persistent plan
region), `selectSession` (joined view of sessionSlice).

## Hook contracts (`hooks/`)

### `useAgentTurn()`

```ts
type UseAgentTurn = {
  sendText: (message: string) => void;        // free-text turn (never sends resume on a fresh session)
  sendAction: (action: UIAction) => void;     // plan-action turn; message = ""
  resumePendingText: (message: string) => void; // reload path: sends with resume: true,
                                                // auto-recovers on 404 (notice + fresh id + resend without resume)
  isStreaming: boolean;                       // input lock
  turns: Turn[];
};
```

Internals: guards re-entry while `isStreaming` (client-side 409 prevention);
calls `api/agent-client.ts`; feeds parser events to the validation gate, then to the
transcript actions above. No abort exposed in MVP: the backend owns the turn once
sent, and a mid-turn abort would only orphan it (client disconnect does not cancel
the in-flight run — Phase 1 research R12).

### `useHealthBadge()`

TanStack Query over `GET {base}/health` → `{ mode: "mock" | "real" | "unknown",
reachable: boolean }`; `staleTime` 30 s; backend down renders the deliberate
"unreachable" state, never a crash.

## Frame parser I/O (`api/sse-frame-parser.ts`)

```ts
type FrameParser = {
  push: (chunk: string) => ParsedEvent[];  // feed raw text; returns events completed by this chunk
  flush: () => ParsedEvent[];              // stream ended: emit a final partial frame if one is buffered
};

type ParsedEvent =
  | { kind: "status"; stage: LifecycleStage; count?: number }
  | { kind: "message_delta"; text: string }
  | { kind: "ui_update"; rawPlan: unknown }            // validated downstream by uiPlanSchema
  | { kind: "turn_end" }
  | { kind: "error"; message: string; code?: string }
  | { kind: "ignored" };                                // unparsable data line / unknown event name (logged, skipped)
```

Parsing rules (per `FRONTEND_GUIDE.md` §4): accumulate; split complete frames on the
`\n\n` separator; keep the trailing partial in the buffer; each frame splits on its
first `\n`; line 1 must start with `event: `, line 2 with `data: `; `JSON.parse` only
the data payload; unknown event names and unparsable payloads yield `ignored`, never
throw. The parser is pure (no fetch, no dispatch) so the chunk-split matrix of SC-002
is a plain unit-test table.

## Lifecycle constants (`constants/lifecycle.ts`)

`LIFECYCLE_STAGES` (the six stages in contracted order), `ALLOWED_ACTIONS_BY_TYPE`
(mirrors the union above; single source for schema + registry wiring),
`SESSION_ID_MIN = 8`, `SESSION_ID_MAX = 64`, `MESSAGE_MAX = 2000`.
