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

## PR 2 — Backend behavior

- [ ] B01 `intent_node` fast-paths: `_refine_params` (flat payload → intent
      keys: sort, anc_only, refine-max-price; battery filter reuses
      `min_battery_hours`) and select_preferences → canonical priorities at
      salience 1.0; both skip the LLM intent call and set `followup=None`.
- [ ] B02 Search + ranking plumbing: `anc_only` + refine-max-price filters
      (combined with budget as the tighter cap); pure post-scoring `sort`
      with `(key, product_id)` tiebreaks; grid emission always carries
      `refinement` (echoing applied state) + chips.
- [ ] B03 D4 amendment: `clarify_gate` routes to `ui_agent_ask_priorities`
      (multi_picker over the five attributes) when category known ∧ no
      priorities ∧ `asked_clarification` false; never twice.
- [ ] B04 `set_quantity` followup kind (resolver + `_build_followup_plan` +
      narration) reusing the cart tools and the amendment anchor; steppers
      emitted per cart line (clamped, ≤ 3 lines).
- [ ] B05 Tests: refine loop (re-rank, no intent call, echoed state),
      select_preferences re-rank, priorities-ask gate table, stepper
      amendment; update exact-action assertions. Backend gates green.

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
