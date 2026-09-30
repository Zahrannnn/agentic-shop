---
description: "Task list for feature implementation"
---

# Tasks: Interactive Registry Expansion v1.1

**Input**: `specs/004-interactive-registry/spec.md`, DECISIONS.md amendment
D11, contract deltas in
`specs/001-backend-agent-scaffold/contracts/ui-dsl.md`, FRONTEND_GUIDE §5.

**Tests**: INCLUDED — backend gate (`uv run ruff check . && uv run ruff
format --check . && uv run pytest`), frontend gate (`npm run verify`), both
green per PR. Stacked branches: contract → behavior → polish.

## PR 1 — Contract + renderers (lockstep) — COMPLETE

- [x] C01 `app/dsl/models.py`: `multi_picker` + `MultiPickerProps`;
      `RefinementSort`/`RefinementFilters`/`RefinementState` on
      `ProductGridProps`; actions `refine`/`set_quantity`/`select_preferences`;
      `ALLOWED_ACTIONS` + `_PROPS_BY_TYPE` updated.
- [x] C02 `app/dsl/validate.py`: payload rules (set_quantity clamp; flat
      refine payloads — unknown keys rejected; select_preferences values ⊆
      options within maxSelect); refine ⇔ refinement coupling (≤ 8 chips).
- [x] C03 Fixtures: grid + cart updated, `multi-picker-priorities.json`
      added; transpiler builders (grid chips, per-line cart actions,
      multi_picker CheckBoxes + Apply) + goldens regenerated.
- [x] C04 Frontend: `plan-schema.ts` mirror (types, bounds, payload
      superRefine, coupling, product-ref rules); `RefinementBar` in
      product-grid; steppers in cart-view; new `multi-picker.tsx` (local
      state + `withValues` stamping); renderer case; fixture lists in the
      three test files; new describes (bar active-state + verbatim chips,
      stepper bounds, multi-picker bound + stamping).
- [x] C05 Docs: DECISIONS.md D11; ui-dsl.md registry/rules/fixture table;
      FRONTEND_GUIDE §5 table. Both gates green.

## PR 2 — Backend behavior — COMPLETE

- [x] B01 `intent_node` fast-paths: `_refine_params` (flat payload, TARGET
      semantics — absent keys reset, making Clear truthful) and
      `_select_preferences_priorities` (canonical priorities at salience
      1.0); both skip the LLM intent call and set `followup=None`.
- [x] B02 Search + ranking plumbing: `anc_only` → `require_anc`;
      refine-max-price tightens (never loosens) the budget cap; pure
      post-scoring `_apply_sort` with product-id tiebreaks; the grid always
      carries `refinement` (echoing applied state) + the chip table
      (fixed targets 40h/$150, active chip omitted, Clear chip when
      deviated, ≤ 8).
- [x] B03 D4 amendment: `clarify_gate` routes to `ui_agent_ask_priorities`
      (multi_picker over the five attribute labels) when category known ∧
      no priorities ∧ no followup ∧ `asked_clarification` false — never
      twice; builder gains the node + edge.
- [x] B04 `set_quantity` followup kind (resolver carries the clamped
      quantity; `_build_followup_plan` applies `app.tools.cart.set_quantity`;
      narration "Quantity for X set to N."); steppers emitted per cart line
      (− at >1, + at <10, ≤ 3 lines).
- [x] B05 Tests: new `tests/test_registry_v11.py` (ask once → answer
      re-ranks → never twice; skip with stated priorities and on
      follow-ups; sort chip re-orders + echoes + Clear appears; filter chip
      + clear; chip turn makes exactly one model call — no intent; stepper
      +/− bounds and amendment) + gate-table and exact-action updates.
      Backend gates green (302 tests).

## PR 3 — Interactive polish + A2UI demo

- [ ] P01 A2UI renderer: multi-picker values stamped from the surface's
      data model (CheckBox two-way bindings + Apply event) — the resolved
      action carries `values` verbatim.
- [ ] P02 A2UI mode verified for the bar + steppers (chips and steps render
      as buttons through the official stack; the smoke test list covers all
      six goldens).
- [ ] P03 Manual mock-mode pass: recommend → refine sort+filter →
      multi-select ask → add to cart → stepper +1 → remove; both renderer
      modes; `npm run verify` + backend gates; commits.
