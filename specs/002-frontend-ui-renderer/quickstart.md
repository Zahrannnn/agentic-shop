# Quickstart — Validate the Frontend UI Renderer & Chat

**Feature**: `002-frontend-ui-renderer`

Runnable proof that the frontend works end-to-end against the frozen Phase 1
backend contract. The automated suite needs no backend; the manual MVP scenario
needs the backend in mock mode (deterministic, instant, no credentials — see
[`specs/001-backend-agent-scaffold/quickstart.md`](../001-backend-agent-scaffold/quickstart.md)
for the backend-side proof).

## Prerequisites

- Node per `frontend/.nvmrc` (22; Next 16 requires >= 20.9) + npm (the boilerplate
  pins `npm@10.2.5` via `packageManager`)
- Python 3.12 + `uv` on PATH, only for the manual scenario's backend
- No API keys anywhere — everything runs in mock mode

## 1. Install and run frontend quality gates (no backend needed)

```bash
cd frontend
npm install
npm run verify        # lint → typecheck → vitest run → production build
```

Expected: all green on a machine with no backend running and no network. The vitest
run includes the fixture contract tests, which read
`backend/fixtures/ui-plans/*.json` directly from the repo (monorepo-root assumption,
research.md R5) — the backend source tree must be present, but the server must not.

## 2. Start the backend (mock mode)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","mode":"mock"}
```

CORS defaults already allow `http://localhost:3000` (the Next dev origin).

## 3. Start the frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000/shop`.

Expected: the shop page loads without any login (route lives in the `(public)`
group), and the health badge shows **mock** within a moment (fed by `GET /health`).
If the badge shows "unreachable", the backend from step 2 is not up or the base URL
env (`NEXT_PUBLIC_AGENT_API_BASE_URL`, default `http://127.0.0.1:8000`) is wrong.

## 4. Manual MVP scenario (mirrors FRONTEND_GUIDE §10 loop: grid → chips → compare → details → cart)

1. **Recommendation turn (US1 + US2)** — send:
   "Help me find the best headphones for long flights under $200. Noise cancellation
   and comfort matter most."
   Expected: input locks immediately; the stepper walks
   `intent_parsed → searching → found_n → researching → ranking → building_ui`; the
   answer text streams in incrementally; a ranked grid of three products replaces the
   placeholder; input unlocks. The transcript keeps the user message and full answer.
2. **Compare (US3)** — tap **Compare** on the grid (or type "compare the first two").
   Expected: a new turn streams exactly like the first and the plan region is
   replaced by a side-by-side table of two products with a single "Choose" CTA. The
   earlier grid turn stays in the transcript with its own plan.
3. **Details (US3)** — tap **Details** (or type "tell me more about this one").
   Expected: a detail card with specs and review quotes.
4. **Cart (US3)** — tap **Add to cart** (or type "add it to my cart"), then check the
   resulting cart view; tap **Remove** and confirm the cart updates.
5. **Clarify chips (US2/US3)** — open a fresh conversation (a new incognito window,
   which generates a new session id) and send "Help me pick a gift".
   Expected: `intent_parsed` then a question with option chips; tapping a chip runs
   the request to completion with no second question.
6. **Resume after reload (US3)** — back in the original conversation, reload the
   page. The transcript is restored and the session id is kept; send a follow-up
   ("what's in my cart?"). Expected: the answer reflects the ongoing session
   (sent with `resume: true`).
7. **Backend restart expiry (US3/US5)** — stop the backend (Ctrl+C), start it again,
   and send another message in the same conversation. Expected: a small
   "session expired — starting fresh" notice and a clean fresh-session answer.
8. **Real-mode latency (US5, optional, needs credentials)** — set `LLM_MODE=real`
   plus the model env in `backend/.env`, restart the backend, and send one request.
   Expected: the badge shows **real**; the stepper tolerates tens of seconds of
   quiet `researching` gaps; no client timeout interrupts the turn.

## 5. Where the contract tests live and what they prove

`frontend/src/features/shopping/validations/ui-plan-schema.test.ts` (run by
`npm run test:run`):

- **All five backend fixtures validate** through the Zod mirror — the client accepts
  exactly what the backend emits (`product-grid-flights`, `preference-picker-category`,
  `comparison-two`, `product-details`, `cart-one-item`), read from
  `backend/fixtures/ui-plans/` as the single source of truth (D8 open item 4).
- **Known-bad mutations are rejected**: an unknown component type, a catalog-foreign
  `productId`, out-of-bounds arrays (grid with 0/7 ids, picker with 5 options,
  comparison with 1/4 ids), and a disallowed action type per component each fail
  validation with a precise issue — the D8 double-sided obligation.
- The catalog id constant is cross-checked against
  `backend/app/catalog/data/headphones.json`, so backend catalog changes fail the
  frontend suite until the mirror is regenerated.

Supporting layers (same suite): the frame parser's chunk-split matrix
(`api/sse-frame-parser.test.ts`) and the component-level streaming harness
(`hooks/use-agent-turn.test.tsx`) with a mocked chunked `fetch`.

## 6. Where to look when something fails

| Symptom | First place to check |
|---|---|
| `npm run verify` red on tests | `validations/ui-plan-schema.test.ts` output vs `backend/fixtures/ui-plans/` (fixtures changed backend-side?) |
| Badge stuck on "unreachable" | backend from step 2 running? `NEXT_PUBLIC_AGENT_API_BASE_URL` in `frontend/.env.local` |
| Turn hangs with no unlock | terminal frame handling in `hooks/use-agent-turn.ts` + `store/transcript-slice.ts` (`turnCompleted`/`turnFailed`/`turnDropped` all unlock) |
| Garbled or lost stream events | `api/sse-frame-parser.ts` (accumulate/split/flush rules) vs `FRONTEND_GUIDE.md` §4 |
| Plan region shows error state on a real turn | `validations/ui-plan-schema.ts` refinement vs `contracts/ui-dsl.md` — and file an issue, never loosen the schema silently |
| CORS errors in the browser console | backend `ALLOWED_ORIGINS` (`contracts/http-api.md`) or proxy via Next route handlers (deployment fallback, research.md R4) |
| Route 404 or auth redirect on `/shop` | route must live in `src/app/(public)/shop/`, not `(app)` (`AuthGate` lives in the `(app)` layout) |
