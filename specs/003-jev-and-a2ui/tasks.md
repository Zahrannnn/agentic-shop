---
description: "Task list for feature implementation"
---

# Tasks: Jev Judgment Layer & A2UI Projection (Phase 2 practice arc)

**Input**: `specs/003-jev-and-a2ui/spec.md`, DECISIONS.md amendments D9/D10,
frozen contracts `specs/001-backend-agent-scaffold/contracts/*`,
`FRONTEND_GUIDE.md`, fixture corpus `backend/fixtures/ui-plans/`

**Tests**: INCLUDED — backend gate `uv run ruff check . && uv run ruff
format --check . && uv run pytest`; frontend gate `npm run verify`. Test-first
within each story; golden fixtures are the contract for PR 2/PR 3.

**Organization**: three independently shippable PRs, each green on its own.

## PR 1 — Jev judgment layer (backend) — COMPLETE

- [x] J01 Extract the intent regex baseline into `backend/app/llm/intent_rules.py`
      (behavior-identical refactor; existing suite proves it).
- [x] J02 `JEV_MODE`/`JEV_API_KEY`/`JEV_MODEL`/`JEV_BASE_URL` in
      `backend/app/config.py` (validated enum `off|mock|real`, `jev_enabled`,
      `require_jev_config` wired into `create_app`).
- [x] J03 `backend/app/llm/jev.py`: wire models, `build_intent_questions`,
      `MockJevClient`, `HttpxJevClient` (retry-once, `JevError`),
      `get_jev`/`reset_jev_cache`, `jev_ask_intent` + `CATEGORY_CONFIDENCE_FLOOR`.
- [x] J04 Intent-node swap in `backend/app/graph/nodes.py` (normal path only;
      chip/follow-up fast paths untouched) + `error` code `jev` in
      `backend/app/api/schemas.py` and `routes.py`.
- [x] J05 Tests `backend/tests/test_jev.py` (equivalence, fast paths,
      transport matrix) + manual `backend/tests/test_jev_real.py` (`-m jev_real`).
- [x] J06 Docs: DECISIONS.md D9, `.env.example`, contract error-code list,
      this spec.

## PR 2 — A2UI transpiler + `a2ui_update` (backend) — COMPLETE

- [x] A01 Golden-fixture test harness: transpile the five
      `backend/fixtures/ui-plans/*.json` and write byte-stable goldens to
      `backend/fixtures/a2ui/` (red first).
- [x] A02 `backend/app/a2ui/transpile.py`: `plan_to_a2ui_messages(plan)`
      — per-turn `createSurface`/`updateComponents`/`updateDataModel`,
      basic-catalog composition of all six component kinds, ChildList
      template + data binding for `product_grid`, lossless action wiring,
      `amendsTurnId` → `deleteSurface` + recreate; version pinned via
      `A2UI_VERSION`.
- [x] A03 Round-trip test: every action reconstructs the verbatim `UIAction`
      (type, label, payload) from the A2UI event.
- [x] A04 Emission: `ui_plan_node`/`ui_agent_ask` emit
      `("a2ui_update", messages)`; `routes.py` defers them with `ui_update`
      (order `ui_update → a2ui_update → turn_end`); SSE-order test; wire
      payload is `{"messages":[…]}` (an object, like every other frame).
- [x] A05 Docs: DECISIONS.md D10, http-api.md optional-event note,
      FRONTEND_GUIDE.md §4 note; goldens committed.

## PR 3 — A2UI rendering path (frontend) — COMPLETE

- [x] F01 Optional `onA2ui` handler + `case "a2ui_update"` in
      `frontend/src/features/shopping/api/agent-client.ts` (+ order and
      opt-out tests; unknown-event tolerance test stays green).
- [x] F02 Sibling blueprint schema `validations/a2ui-schema.ts` (pinned
      catalog id + `v0.9` message subset) + golden-fixture acceptance and
      rejection tests; `uiPlanSchema` untouched (only `PLAN_ACTION_TYPES`
      gained an export).
- [x] F03 Store: additive `Turn.blueprint` + `blueprintReceived`/
      `blueprintAmended` reducers (no-op after terminal) in
      `store/transcript-slice.ts`.
- [x] F04 Renderer: `components/a2ui/a2ui-renderer.tsx` on the OFFICIAL
      `@a2ui/react` + `@a2ui/web_core` (v0.9) — the zod-v4 peer risk was
      resolved empirically (all five goldens process; the fallback processor
      was not needed); actions reconstruct the verbatim `UIAction` (proven
      by a click test through the real renderer); `data-testid="a2ui-*"`.
- [x] F05 Toggle in `shop-page.tsx` header (ephemeral state; native fallback
      with notice when a turn has no blueprint); `npm run verify` green
      (189 tests).
