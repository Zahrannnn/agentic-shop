# Agentic Shopping System — Architecture Decision Record

**Project:** Agentic Shopping MVP (practice: agentic frontend)
**Status:** Locked v1.0 — 2026-08-29
**Source:** PRD v0.1 draft + design discussion

---

## D1 — UI surface model: transcript with inline UI cards ✅

Chat-style transcript where each agent turn appends `message + rendered UI plan`.
- History, scrollback, context = free
- Matches industry convergence (Vercel AI SDK chat UIs, ChatGPT apps)
- Rejected: single repaintable "stage" (must invent history/back-nav)

## D2 — UI plans replace, never patch ✅

Each agent turn emits **one full UI plan** that replaces the previous turn's plan region.
- Patching/diffing UI plans → explicit **V2** backlog item
- Eliminates ambiguity of "replace or augment" in PRD §6

## D3 — Ranking: deterministic scorer + LLM narration ✅

1. LLM translates preferences → numeric weights (structured output, temp 0)
2. Pure Python function scores catalog: `score = Σ(weight_i × normalized_attr_i)` — unit-tested
3. LLM narrates top-3 with reasons referencing computed attributes
- LLM never decides order. Identical input → identical ranking.

## D4 — Clarify gate: rule-based, not LLM-decided ✅

- Category missing/unknown → ask (max 1 question, with option chips)
- Budget missing → proceed with sensible category cap, state assumption
- Contradictory constraints → proceed with closest matches, flag honestly
- Never ask twice in a row; after any answer, run to completion
- Implemented as a deterministic check node, not an LLM judgment

## D5 — Catalog: curated JSON, ~28 headphones ✅

Pydantic `Product`: `price_usd, battery_hours, weight_g, anc_type, driver_mm, codecs, multipoint, folding`
- **Reviews pre-scored per attribute** `{comfort: 4.6, anc: 4.8, sound: 4.2}` + 4–6 short quotes per product
- Research Agent reads scores/quotes — never does NLP extraction at runtime
- Flights scenario has 4 genuine winners with different tradeoff profiles
  (battery king / comfort king / ANC king / value pick) so compare is interesting

## D6 — Graph: fixed backbone + one conditional edge ✅

```
intent → clarify_gate ─(ask)→ ui_agent(ask) → [end turn]
              └─(proceed)→ search → research → recommend → ui_plan → respond
```
- Only `clarify_gate` is conditional (deterministic)
- `MemorySaver` checkpointer, `thread_id` = session id
- Turn ends at `respond` or `ask`; next user message resumes from state
- Free routing / dynamic supervisor → V2
- temp 0, one model for all nodes in MVP

## D7 — Transport: SSE with first-class lifecycle events ✅

Plain FastAPI `StreamingResponse`, no websockets.

```
event: status        data: {"stage":"searching"}          # intent_parsed|searching|found_n|researching|ranking|building_ui
event: status        data: {"stage":"found_n","count":24}
event: message_delta data: {"text":"..."}                 # assistant prose tokens
event: ui_update     data: {<full UI plan>}               # validated DSL
event: turn_end      data: {}
event: error         data: {"message":"..."}
```

Frontend contract:
- first `status` → **lock** previous plan + show progress stepper
- `ui_update` → render new plan (D2: full replace)
- `turn_end` → unlock
- No ghost UI, no double-submit

## D8 — Stack (locked) ✅

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn, deps via `uv` |
| Agents | LangGraph + langchain-core, Pydantic v2 structured outputs |
| LLM | **OpenCode gateway (user's plan), OpenAI-compatible** — model = env config, swappable |
| Transport | SSE (D7) |
| Frontend | **User's Next.js boilerplate** (pending — see Open Items) |
| UI primitives | Tailwind + shadcn/ui; registry components wrap shadcn |
| DSL validation | Pydantic (backend) + Zod (frontend); shared `fixtures/ui-plans/*.json` + contract tests both sides |
| Client state | zustand |
| Pkg manager | pnpm (frontend), uv (backend) |

### LLM wiring

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.LLM_MODEL,  # e.g. from /models on user's plan
    api_key=settings.OPENCODE_API_KEY,
    base_url=settings.OPENCODE_BASE_URL,  # OpenCode gateway /v1 endpoint
    temperature=0,
)
structured = llm.with_structured_output(SomePydanticModel)
```

Required resilience wrapper (open-weight/free models are flakier):
- Pydantic-validate every structured output
- On failure: 1 retry with validation error fed back, then hard `error` event
- Model never hard-coded; swap via `.env` without code changes

---

## MVP scenario (acceptance)

"Help me find the best headphones for long flights under $200."
Understand → search → research → rank → dynamic ProductGrid → interact
→ comparison UI → explained recommendation → add to mock cart — all inside
one transcript conversation.

## Open items

1. ~~Frontend boilerplate~~ — resolved: `corelia-next-boilerplate` adopted as
   `frontend/` (monorepo, PR #5)
2. **Exact model ID** — pick from user's plan `/models` (needs reliable
   structured output; wrapper in D8 covers variance; muse-spark free tier
   works today via env)
3. ~~Repo init~~ — resolved: monorepo (PR #5)
4. Zod ↔ Pydantic contract: single source of truth = `fixtures/ui-plans/` +
   contract tests on both sides

## Amendments (2026-08-30 — owner-directed Phase 2 polish)

- **D2 amendment — bounded plan amendment (V2 first slice).** Full
  diff-patching stays rejected (the transcript renders per-turn plans; diffs
  only make sense for a repaintable stage). Unlocked in bounded form: a
  `cart_view` plan MAY carry `amendsTurnId` referencing the earlier cart plan
  it replaces — the client updates that turn's plan region in place instead of
  appending a duplicate cart section. Everything else remains full-replace.
- **D5 amendment — multi-category catalog.** The catalog MAY carry more than
  one category (starts with headphones + earbuds). Category-specific budget
  defaults replace the single hard-coded cap; the clarify chips and search are
  already category-generic.
- **Latency UX (real mode).** The FE thinking state carries an elapsed-time
  counter and reassurance rotation; pipeline stage names stay unrendered.

## V2 backlog (explicitly deferred)

- Full plan diff-patching beyond the bounded cart amendment above
- Free-form agent routing / dynamic supervisor (D6)
- More components beyond MVP registry set
- Real product APIs, payments, checkout
