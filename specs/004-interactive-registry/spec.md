# Feature Specification: Interactive Registry Expansion v1.1

**Feature Branch**: `004-interactive-registry`

**Created**: 2026-09-29

**Status**: In progress (PR 1 on `feat/registry-v11-contract`, stacked on the
merged 003 arc branches)

**Input**: Owner-directed: "i want the agent to have more components to make
the experience more interactive". Binding architecture record: DECISIONS.md
amendment **D11**. The chosen set (mock checkout was considered and dropped):
refinement bar on the grid, cart quantity steppers, multi-select priorities
ask.

## User Stories & Testing

### US1 — Refinement bar (P1)

Every recommendation grid carries a refinement bar: sort chips
(relevance/price ↑/price ↓/top-rated) and filter chips (ANC only, 40h+
battery, under $X). Tapping a chip posts its `refine` action verbatim; the
agent re-runs search + ranking with the new constraints and emits a fresh
grid whose `refinement` echoes the applied state (the active chip renders
pressed). No intent re-parse — the loop is one fast turn.

**Independent Test**: mock-mode conversation: recommend → tap "Price: low to
high" → the next grid is price-ordered with `refinement.sort =
"price_asc"`; the intent LLM call never fires (`fake.calls` has no
`IntentExtraction`); chip click → verbatim payload on the wire.

### US2 — Cart quantity steppers (P1)

Cart rows render −/+ stepper controls from `set_quantity` actions (clamped
1–10 at emission; no "+" at 10, no "−" at 1). Tapping posts the step
verbatim and the cart re-renders via the existing amendment anchor.

**Independent Test**: add to cart → tap "+" → quantity 2, total doubled, the
earlier cart turn's plan region updated in place; at quantity 10 only "−"
ships.

### US3 — Multi-select priorities ask (P2, D4 amendment)

When the category is known but no priorities were stated (and nothing asked
yet), the clarify gate asks "What matters most? Pick up to 2." through the
new `multi_picker` before recommending. The user checks options (bounded by
`maxSelect`, unchecked rows disable at the bound) and taps the apply action,
whose `values` the renderer stamps from local state. The gate never asks
twice (`asked_clarification` guard); conversations that state priorities
skip it entirely.

**Independent Test**: "best headphones under $200" → priorities ask fires
exactly once; answering re-ranks; "headphones with great battery" → no ask.
Schema accepts the `multi-picker-priorities` fixture and rejects filled
`values` outside options or over `maxSelect`.

## Contract deltas (all mirrored in `ui-dsl.md` / FRONTEND_GUIDE §5)

- Component registry 6 → 7 (`multi_picker`); action vocabulary 6 → 9
  (`refine`, `set_quantity`, `select_preferences`).
- `product_grid` props gain optional `refinement`; strict state ⇔ chips
  coupling; flat refine payloads (A2UI context constraint).
- Fixture corpus: `product-grid-flights` and `cart-one-item` updated,
  `multi-picker-priorities` added; A2UI goldens regenerated in lockstep.

## Assumptions

- Free-text equivalents ("set the first one to 3") stay out of scope; the
  actions are the interface.
- The flat refine payload is a deliberate A2UI-driven constraint, documented
  in D11 — no nested payload objects anywhere in the action vocabulary.
- The stamping exception now has exactly two members (`withProduct`,
  select_preferences `values`); any third needs a DECISIONS entry.
