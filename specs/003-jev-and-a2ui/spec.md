# Feature Specification: Jev Judgment Layer & A2UI Projection (Phase 2 practice arc)

**Feature Branch**: `003-jev-and-a2ui`

**Created**: 2026-09-29

**Status**: Complete (PR 1 `feat/jev-intent-judgment`, PR 2
`feat/a2ui-projection`, PR 3 `feat/a2ui-renderer`)

**Input**: Owner-directed practice — adopt two 2026 agent-stack technologies
in small, additive slices: **TypeSafe Jev** (the "System One" typed-decision
model, docs.typeSafe.ai) replacing the intent LLM call, and the **A2UI v0.9
protocol** (Google's agent-to-UI spec, github.com/a2ui-project/a2ui) as a
second, additive rendering of the same UI plans. Binding architecture record:
DECISIONS.md amendments **D9** (judgment layer) and **D10** (A2UI projection).

## Scope

Three independently shippable PRs; default behavior of `main` is unchanged
(`JEV_MODE=off` keeps the LLM intent path; the new SSE event is ignored by the
existing frontend by contract).

1. **PR 1 — backend**: `app/llm/jev.py` judgment factory
   (off/mock/real mirroring `app/llm/client.py`), one batched intent
   judgment (category Choice + per-attribute Score rubrics), the intent-node
   swap, `error` code `jev`, real-mode measurement tests (`-m jev_real`).
2. **PR 2 — backend**: pure `UIPlan → A2UI v0.9 message stream` transpiler +
   golden fixtures + optional `a2ui_update` SSE event (emitted after
   `ui_update`, before `turn_end`).
3. **PR 3 — frontend**: consume `a2ui_update` (optional handler — never fails
   a turn), Zod blueprint schema, per-turn blueprint state, an A2UI renderer
   path, and a native/A2UI toggle in the shop header.

## User Stories & Testing

### US1 — Intent as one typed judgment (P1, PR 1)

With `JEV_MODE=mock|real`, the shopper's message is parsed by ONE batched Jev
request instead of an LLM structured-output call. Chip answers and follow-up
phrases never trigger a judgment (they resolve deterministically, D4/D6). A
Jev failure after its single retry ends the turn with one `error` frame
(code `jev`) — never a partial turn, never a silent fallback to the LLM.

**Independent Test**: `JEV_MODE=mock` full turn produces byte-identical SSE
output to the LLM path for the MVP message (session id normalized); a raised
`JevError` yields exactly one terminal `error`/`jev` frame and no `turn_end`.

### US2 — Plans projected to A2UI (P2, PR 2)

Every emitted UI plan is additionally transpiled — by pure, unit-tested code
— into an A2UI v0.9 message stream (`createSurface` / `updateComponents` /
`updateDataModel`, basic catalog, per-turn `surfaceId`, cart amendments as
`deleteSurface`+recreate) and streamed as one optional `a2ui_update` frame
after `ui_update`. The frozen DSL contract (`ui_update`) is untouched; the
transpiler is a projection, never a second source of truth (D10).

**Independent Test**: the five `backend/fixtures/ui-plans/*.json` documents
transpile to byte-stable golden fixtures under `backend/fixtures/a2ui/`;
actions round-trip losslessly (event name + context reconstruct the verbatim
`UIAction`); the SSE order `ui_update → a2ui_update → turn_end` holds.

### US3 — Native vs A2UI rendering, side by side (P2, PR 3)

The shop header carries a renderer toggle. In A2UI mode each turn's plan
region renders from the blueprint through the A2UI stack; turns without a
blueprint (backend without emission) fall back to the native renderer with a
small notice. Tapping any action in either mode posts the SAME verbatim
`UIAction` object. An invalid blueprint is ignored — the native plan still
renders and the turn never fails because of the blueprint.

**Independent Test**: mock-mode conversation renders identically useful
output in both modes; blueprint schema accepts all golden fixtures and
rejects unknown components/foreign catalog ids; `npm run verify` green with
no backend running except for the fixture files it reads from disk.

## Key Decisions (bound to DECISIONS.md)

- **D9**: judgment factory + `JEV_MODE` tri-state + `CATEGORY_CONFIDENCE_FLOOR`
  + shared `app/llm/intent_rules` baseline for both mocks + `use_case` not
  produced (no consumers) + budget via dollar regex (numbers are code's job).
- **D10 (PR 2)**: A2UI is an additive projection; wire version pinned `v0.9`
  via one module constant; the frozen D2/D7 DSL contract stays the truth.

## Assumptions

- TypeSafe Jev is in early access; the API surface here (`POST /v1/systemone`,
  state + questions map, Noul/Choice/Score answers) is the documented one and
  may drift — `HttpxJevClient` isolates it behind `app/llm/jev.py`.
- A2UI v0.9.1 is the current production spec (v1.0 is a breaking RC); the
  official `@a2ui/react` renderer peers on `zod ^3` — if that conflicts with
  the frontend's Zod v4 beyond resolution, the pre-approved fallback is a
  minimal in-repo message processor rendering through the existing six
  styled components.
- Real-mode measurements (`-m jev_real`) are manual observations with the
  owner's API key, never CI gates.
