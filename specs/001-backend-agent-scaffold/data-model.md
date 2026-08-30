# Data Model — Agentic Shopping Backend (Phase 1 Scaffold)

**Feature**: `001-backend-agent-scaffold` | **Date**: 2026-08-29

All models are Pydantic v2 unless marked as a LangGraph state type (TypedDict).
Field names are snake_case in Python; the UI DSL and protocol events serialize
to the camelCase JSON contract in [contracts/](./contracts/) exactly as locked
in DECISIONS.md.

## Catalog entities

### Product

One curated catalog item (`backend/app/catalog/data/headphones.json`).

| Field | Type | Rules |
|---|---|---|
| `id` | `str` | stable slug, unique, e.g. `"aurora-hush-pro"` |
| `name` | `str` | display name |
| `brand` | `str` | — |
| `category` | `str` | `"headphones"` in MVP |
| `price_usd` | `float` | > 0 |
| `battery_hours` | `float` | > 0 |
| `weight_g` | `float` | > 0 |
| `anc_type` | `enum` | `none \| passive \| active \| adaptive` (ordinal 0–1 for scoring) |
| `driver_mm` | `float` | > 0 |
| `codecs` | `list[str]` | subset of `{sbc, aac, aptx, aptx_hd, ldac, lc3}` |
| `multipoint` | `bool` | — |
| `folding` | `bool` | — |
| `review_scores` | `ReviewScores` | see below |
| `quotes` | `list[str]` | 4–6 short review quotes |

**ReviewScores** — pre-scored per attribute (D5), each `0.0–5.0`, one decimal:
`comfort, anc, sound, battery, value`. The research node reads these; it never
parses quote text at runtime (FR-005).

**Validation**: loader validates every record and fails loudly on the first
malformed item; duplicate ids are a load error. Dataset size MUST be 28
(±1 tolerated by tests, not by the acceptance criteria of D5).

## Agent-workflow entities

### UserIntent

Accumulated understanding of what the shopper wants; merged across turns.

| Field | Type | Rules |
|---|---|---|
| `category` | `str \| None` | must be a known catalog category when set |
| `budget_usd` | `float \| None` | > 0 |
| `use_case` | `str \| None` | free text, e.g. `"long flights"` |
| `priorities` | `dict[str, float] \| None` | named attribute → salience; LLM turns this into `PreferenceWeights` |
| `assumptions` | `list[str]` | stated assumptions (e.g. budget cap applied) |
| `flag_contradiction` | `bool` | constraints cannot all be satisfied |

### PreferenceWeights (structured LLM output)

`{battery, comfort, anc, sound, value}` each `0.0–1.0`, one per scorable
attribute. Emitted per turn by the `recommend` node's model call (temp 0).
Normalized to sum 1 by the scorer — the model is never trusted with sums.

### ScoredProduct

Output of the pure scorer per candidate:

| Field | Type | Rules |
|---|---|---|
| `product_id` | `str` | references `Product.id` |
| `score` | `float` | deterministic |
| `contributions` | `dict[str, float]` | attribute → weighted contribution; sums to `score` |
| `rank` | `int` | 1-based; ties broken by lexicographic `product_id` |

### ClarifyQuestion (structured output of the ask path)

`question: str` (max 1 question, D4) + `options: list[str]` (chip labels,
3–4). Produced deterministically by the gate (catalog categories + "Something
else"), not by the LLM.

### Node structured-output models (`app/graph/schemas.py`)

Every LLM call in the graph requests exactly one of:

- `IntentExtraction` — `{category?, budget_usd?, use_case?, priorities?,
  ui_action?}` parsed from the user turn (merged into `UserIntent` by code).
- `PreferenceWeights` — see above.
- `Narration` — `{intro, per_product: list[{product_id, reason}], outro}`;
  `product_id`s are validated against the catalog and invalid ones dropped.
- `PlanSelection` — `{component: enum(component types), title, product_ids?}` —
  the ui_plan node's *choice* of component; the plan document itself is
  assembled deterministically from ranked data (the LLM configures, never
  free-writes the plan).

## Session state (LangGraph `ShoppingState`, TypedDict)

| Key | Type | Notes |
|---|---|---|
| `messages` | `list` | transcript (user + assistant turns) |
| `intent` | `UserIntent` | accumulated |
| `asked_clarification` | `bool` | gate anti-loop flag (never ask twice in a row) |
| `candidates` | `list[Product]` | current search results |
| `ranked` | `list[ScoredProduct]` | current ranking (top-N presented) |
| `selected_ids` | `list[str]` | products referenced for compare/details |
| `plan` | `UIPlan \| None` | current turn's plan (full replace each turn, D2) |
| `cart` | `list[CartItem]` | per-session mock cart |
| `turn_in_flight` | `bool` | busy-lock source for FR-016 |

Persisted only by `MemorySaver` keyed on `thread_id` = session id (in-memory,
restart = fresh sessions — accepted in spec assumptions).

**State transitions (fixed backbone, D6):**

```
START → intent → clarify_gate ──(ask)──→ ui_agent_ask ──→ END (turn ends)
                     │
              (proceed)→ search → research → recommend → ui_plan → respond → END
```

- The only conditional edge is `clarify_gate` (pure rule table, R7).
- A later user message resumes from checkpointed state; `asked_clarification`
  guarantees run-to-completion after an answer.

## UI DSL entities (`app/dsl/models.py`)

### UIPlan

| Field | Type | Rules |
|---|---|---|
| `plan_version` | `str` | `"1"` in MVP |
| `session_id` | `str` | echo of the session |
| `turn_id` | `int` | monotonically increasing per session (no wall clock — determinism); matches the wire contract and fixtures |
| `root` | `ComponentNode` | exactly one root component |

### ComponentNode

| Field | Type | Rules |
|---|---|---|
| `type` | `enum` | `product_grid \| preference_picker \| comparison_table \| product_details \| cart_view \| text_block` |
| `props` | discriminated per type | see below |
| `actions` | `list[UIAction]` | must ⊆ allowed actions for the type |

Prop contracts per component (MVP registry):

- `product_grid`: `{title, product_ids: list[str] (1–6), ranked: bool}`
- `preference_picker`: `{question, options: list[str] (3–4), attribute_values?}`
- `comparison_table`: `{product_ids: list[str] (2–3), attributes: list[str]}`
- `product_details`: `{product_id, show_quotes: bool}`
- `cart_view`: `{items: list[{product_id, quantity}], total_usd}`
- `text_block`: `{heading?, body}`

**Validation rules** (enforced before any `ui_update` emission, FR-008/SC-004):
unknown `type` → invalid; every `product_id` MUST exist in the catalog;
`actions` MUST be from the type's allowed set (`product_grid`: compare,
details, add_to_cart; `comparison_table`: choose; `preference_picker`:
select_preference; `product_details`/`cart_view`: none in MVP; `text_block`:
none); counts per component bounds above; no nested `children` in MVP
(flat registry).

### UIAction

`{type: enum(compare, details, select_preference, add_to_cart, remove_from_cart,
choose), label, payload: dict}` — the shape the frontend echoes back inside a
follow-up `ChatRequest.ui_action`.

## Protocol entities (`app/api/schemas.py`)

### ChatRequest (client → server, JSON body)

`{session_id: str (uuid-ish, client-generated), message: str (1–2000 chars),
ui_action?: UIAction}`

### ProtocolEvent (server → client, SSE frames per D7)

| `event:` | `data:` | Notes |
|---|---|---|
| `status` | `{stage, count?}` | stages in order: `intent_parsed, searching, found_n, researching, ranking, building_ui` |
| `message_delta` | `{text}` | prose increments of the answer |
| `ui_update` | `{...UIPlan}` | validated DSL; full replace (D2) |
| `turn_end` | `{}` | unlocks the client |
| `error` | `{message, code?}` | ends the turn; codes: `structured_output`, `busy`, `unknown_session`, `internal` |

**Ordering contract**: per turn — zero or more `status`, zero or more
`message_delta`, at most one `ui_update` (ask-turns emit the picker plan,
answered-turns may re-emit), exactly one terminal `turn_end` or `error`.

### CartItem

`{product_id: str, quantity: int (1–10)}`; cart totals computed from catalog
prices only.
