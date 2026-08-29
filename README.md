# agentic-shop

Multi-agent AI shopping experience — **the UI is an output of the agent, not the place
where the agent operates.** Practice project for agentic frontend patterns.

You talk to a shopping agent in a transcript; every agent turn streams back a
conversational answer plus a **validated UI plan document** that the frontend renders
(product grids, comparison tables, preference chips, cart views). No traditional
pages, no navigation.

MVP scenario: *"Help me find the best headphones for long flights under $200."*

## Status

| Phase | Scope | State |
|---|---|---|
| 1 | Backend: LangGraph agent graph, catalog, tools, UI DSL, SSE API | ✅ implemented (`specs/001-backend-agent-scaffold/`) |
| 2 | Frontend: Next.js renderer for the UI plan DSL | ⬜ waiting on owner-supplied boilerplate |

## How it works

```text
user message ──▶ POST /api/chat ──▶ LangGraph pipeline (fixed backbone)
                                    intent → clarify_gate ─(ask)→ ui_agent_ask ─▶ END
                                                └─(proceed)→ search → research
                                                            → recommend → ui_plan
                                                            → respond ─▶ END
SSE back:  status … → message_delta … → ui_update (validated UI plan) → turn_end
```

Design invariants (locked in [`DECISIONS.md`](DECISIONS.md)):

- **Deterministic ranking** — the LLM only proposes preference *weights*; a pure,
  unit-tested scorer computes the order. Identical input → identical ranking.
- **Structured outputs or no outputs** — every model call is schema-validated, retried
  once with the validation error fed back, then fails with a clean `error` event.
- **UI plans are data, never code** — each turn emits one full plan that validates
  against a shared fixture corpus (`backend/fixtures/ui-plans/`); the future frontend
  mirrors the same contract in Zod.
- **Rule-based clarify gate** — missing category asks exactly one chip question;
  missing budget or contradictory constraints proceed with honest disclosures.

## Quickstart (no API key needed)

```bash
cd backend
uv sync
uv run pytest                      # 194 tests, fully offline in mock mode
uv run uvicorn app.main:app --reload
```

Then, in another terminal:

```bash
curl http://127.0.0.1:8000/health
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-12345","message":"Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most."}'
```

You'll see `status` progress events, streamed answer text, one `ui_update` plan, and a
`turn_end`. Full walkthrough (clarify path, compare, cart, determinism check):
[`specs/001-backend-agent-scaffold/quickstart.md`](specs/001-backend-agent-scaffold/quickstart.md).

### Real model

Point `backend/.env` at [OpenCode Zen](https://opencode.ai/docs/zen/) (see
`backend/.env.example`; never commit `.env`):

```bash
LLM_MODE=real
LLM_MODEL=muse-spark-1.2-contributor-free   # free Zen model
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_KEY=<your key>
LLM_API_STYLE=responses                     # muse is Responses-API-only
```

The model is swappable via env only — all model access goes through
`backend/app/llm/client.py`, which validates every structured output and falls back to
schema-in-prompt JSON mode for Responses-only models.

## Repository

```text
├── PRD.md                     product requirements (v0.1 MVP)
├── DECISIONS.md               locked architecture decisions (binding, D1–D8)
├── AGENTS.md                  crew guide for coding agents
├── specs/001-backend-agent-scaffold/   spec → research → plan → contracts → tasks
├── .specify/                  GitHub Spec Kit (constitution, templates, scripts)
└── backend/
    ├── app/llm/               the ONLY doorway to any model (factory + mock mode)
    ├── app/catalog/           curated 28-item headphone dataset + loader
    ├── app/ranking/           pure deterministic scorer
    ├── app/tools/             search, pre-scored research, mock cart
    ├── app/graph/             LangGraph nodes, state, builder
    ├── app/dsl/               UI plan schemas + validation
    ├── app/api/               /health + /api/chat (SSE)
    ├── fixtures/ui-plans/     shared DSL contract corpus
    └── tests/                 194 pytest tests (scorer, tools, DSL, SSE, graph)
```

## Development

- Python 3.12 + [`uv`](https://docs.astral.sh/uv/); quality gates before any PR:
  `uv sync && uv run ruff check . && uv run ruff format --check . && uv run pytest`
  (from `backend/`)
- [pre-commit](.pre-commit-config.yaml) hooks: `uv tool install pre-commit && pre-commit install`
- Conventional Commits; feature work flows through the Spec Kit skills
  (`$speckit-specify` → plan → tasks → implement); every plan is checked against the
  project constitution (`.specify/memory/constitution.md`)
- Frontend phase lands later on a Next.js boilerplate — pnpm, Tailwind + shadcn/ui,
  zustand, Zod mirrors of the plan DSL
