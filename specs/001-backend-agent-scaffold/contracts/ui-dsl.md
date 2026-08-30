# Contract: UI Plan DSL + Shared Fixture Corpus

**Feature**: `001-backend-agent-scaffold` | **Date**: 2026-08-29

The UI plan is the agent↔frontend contract (PRD §14, DECISIONS.md D2/D8).
The single source of truth is the fixture corpus `backend/fixtures/ui-plans/*.json`:
Pydantic (backend, this phase) and Zod (frontend, later phase) must both accept
every fixture and reject known-bad mutations. Emitting camelCase JSON is part
of the contract — the examples below are wire format.

## Plan envelope (wire format)

```json
{
  "planVersion": "1",
  "sessionId": "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
  "turnId": 3,
  "root": { "type": "...", "props": { }, "actions": [ ] }
}
```

Full-replace rule (D2): every plan is standalone; a renderer MUST NOT need the
previous plan to render a new one.

**Bounded amendment (D2 amendment):** a `cart_view` plan MAY additionally
carry `"amendsTurnId": <int ≥ 1>` — the `turnId` of the earlier cart plan turn
it supersedes. A client that still shows that turn's plan MUST replace it in
place (the cart region stays a single authoritative section) instead of
appending a duplicate cart section; the amending turn itself renders its prose
only (no plan of its own). The amending document keeps its own newer `turnId`
— `turnId` identifies the turn, `amendsTurnId` points at the anchored region.
If the referenced turn is unknown to the client (e.g. after a reload), it
falls back to normal full-replace rendering of the amending plan. Every other
component kind stays strictly full-replace: the backend rejects
`amendsTurnId` on any non-`cart_view` root. The field is absent from the wire
document when unset (fixtures stay non-amending).

## Component registry (MVP set) and props

### `product_grid`

```json
{
  "type": "product_grid",
  "props": {
    "title": "Best matches for long flights",
    "productIds": ["aurora-hush-pro", "skyline-hush", "cloudline-air"],
    "ranked": true
  },
  "actions": [
    { "type": "compare", "label": "Compare" },
    { "type": "details", "label": "Details" },
    { "type": "add_to_cart", "label": "Add to cart" }
  ]
}
```

Rules: 1–6 `productIds`; `ranked` true means order is the recommendation
order. Allowed actions: `compare`, `details`, `add_to_cart`.

### `preference_picker` (clarify chips)

```json
{
  "type": "preference_picker",
  "props": {
    "question": "Which category are you shopping for?",
    "options": ["Headphones", "Something else"]
  },
  "actions": [
    { "type": "select_preference", "label": "Headphones", "payload": { "value": "headphones" } }
  ]
}
```

Rules: 3–4 options normally (fewer allowed for the category ask); every option
MUST have a matching `select_preference` action. Allowed action:
`select_preference`.

### `comparison_table`

```json
{
  "type": "comparison_table",
  "props": {
    "productIds": ["aurora-hush-pro", "cloudline-air"],
    "attributes": ["price_usd", "battery_hours", "weight_g", "anc_type", "comfort"],
    "values": {
      "aurora-hush-pro": { "price_usd": 179.0, "anc_type": "adaptive", "comfort": 4.7 },
      "cloudline-air": { "price_usd": 139.0, "anc_type": "active", "comfort": 4.9 }
    }
  },
  "actions": [
    { "type": "choose", "label": "Choose Aurora Hush Pro", "payload": { "productId": "aurora-hush-pro" } }
  ]
}
```

Rules: 2–3 `productIds`; attributes restricted to catalog attribute names.
`values` (optional, added post-review): `{productId: {attribute: string|number|boolean|null}}`
render aid so clients show real values without a catalog lookup; when present its
keys must be a subset of `productIds` and attribute keys inside the whitelist.
Allowed action: `choose` (max one).

### `product_details`

```json
{
  "type": "product_details",
  "props": { "productId": "aurora-hush-pro", "showQuotes": true },
  "actions": []
}
```

### `cart_view`

`cart_view` is the only component that may carry the envelope's optional
`amendsTurnId` (see "Plan envelope" above): the first cart mutation emits a
standalone plan; every later cart turn supersedes that anchored plan in place.

```json
{
  "type": "cart_view",
  "props": {
    "items": [ { "productId": "aurora-hush-pro", "quantity": 1 } ],
    "totalUsd": 179.0
  },
  "actions": [
    { "type": "remove_from_cart", "label": "Remove", "payload": { "productId": "aurora-hush-pro" } }
  ]
}
```

### `text_block`

`{ "heading"?: string, "body": string }` — used for assumption/contradiction
disclosures; no actions.

## Validation rules (enforced backend-side before `ui_update`; mirrored in Zod later)

1. Envelope: `planVersion == "1"`; `sessionId` non-empty; `turnId` ≥ 1 int;
   optional `amendsTurnId` ≥ 1 int (`cart_view` roots only — D2 amendment).
2. `root.type` ∈ registry; unknown type is invalid (never forward-compatible
   fallback rendering).
3. Every `productId` referenced anywhere MUST exist in the catalog.
4. `actions` per component ⊆ allowed set for that type; action labels
   non-empty; payloads schema-conformant.
5. Collection bounds as listed per component (productIds, options, items).
6. No executable content of any kind — the plan is data only (PRD §14).

## Fixture corpus (source of truth)

`backend/fixtures/ui-plans/` — created in this phase, reused verbatim by the
frontend phase:

| Fixture | Covers |
|---|---|
| `product-grid-flights.json` | US1 recommendation turn |
| `preference-picker-category.json` | US2 clarify turn |
| `comparison-two.json` | US4 compare turn |
| `product-details.json` | US4 inspect turn |
| `cart-one-item.json` | US4 cart turn |

Every fixture MUST validate against the backend DSL models
(`tests/test_dsl.py` round-trips each through Pydantic and compares
semantically), and the graph in mock mode MUST emit plans equivalent to these
for the corresponding scenario turns (contract test). Known-bad mutations
(unknown type, foreign productId, out-of-bounds list, disallowed action) are
kept as inline test cases, not fixtures.

## Serialization rules

- Backend emits camelCase wire format (Pydantic `alias_generator=to_camel`,
  `populate_by_name=True`); internal Python stays snake_case.
- Emission path: DSL models → `model_validate` → serialize → SSE `ui_update`.
  A plan that fails validation is never sent; the turn ends with
  `error/structured_output` (FR-008, SC-004).
