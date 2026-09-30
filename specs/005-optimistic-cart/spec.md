# Feature Specification: Optimistic Cart (D12)

**Feature Branch**: `005-optimistic-cart`

**Created**: 2026-09-30

**Status**: In progress

**Input**: Owner report — stepper taps "take space and time": a full streamed
turn per tap, confirmation prose stacking, and duplicate cart tables from the
second tap on. Binding record: DECISIONS.md **D12**.

## Root causes

1. Widget taps rode the conversational pipeline (a whole turn — in real mode
   seconds — with input lock and a streamed confirmation).
2. The client's amendment-anchor lookup keyed on the anchored plan's
   `turnId`, which the FIRST amendment itself overwrites (the replacement
   plan carries the new turn's id) — so from the second mutation on, the
   anchor lookup failed and carts stacked as new tables.

## The fix (two PRs)

**PR 1 (backend)**: `CartLine` gains `unitPriceUsd`; new `PATCH /api/cart`
mutates the LangGraph checkpoint directly (`get_state`/`update_state`) and
answers with the authoritative re-rendered plan + A2UI projection. Guards:
404 unknown session/line, 409 while a turn streams. No LLM, no lock.

**PR 2 (frontend)**: the anchor is remembered by a stable flag (stacked-tables
bug fixed); stepper taps dispatch an optimistic patch (instant quantity +
total from unit prices), persist via PATCH, and reconcile against the
response. No transcript turn, no input lock, no confirmation prose.

## Acceptance

- Tap "+" twice fast: ONE cart table, counts update in the same frame as the
  tap, totals exact (from unit prices), no transcript noise.
- "What's in my cart?" after patches reflects the patched checkpoint.
- "Set the second one to 3" (conversational) still works as a normal turn.
- Backend restart → PATCH 404s with `unknown_session` (in-memory sessions).

## Out of scope

Line-price display column, retry queues, multi-tab sync.
