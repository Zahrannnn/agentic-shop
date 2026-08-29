# AGENTS.md — crew guide for agentic-shop

Multi-agent AI shopping system: a LangGraph agent backend generates UI plans (structured DSL),
a Next.js frontend renders them. **Read `DECISIONS.md` before writing any code — it is the
binding architecture record. The PRD (`PRD.md`) describes product intent; where they differ,
`DECISIONS.md` wins.**

## Current phase

**Phase 1 — backend scaffold.** The `frontend/` directory does not exist yet (owner will
supply a Next.js boilerplate). Do not create frontend code, package.json files, or React
components. Backend work only until the owner says otherwise.

## Backend conventions

- Location: `backend/`
- Python 3.12, dependencies managed with **uv** (`uv add`, `uv run`)
- FastAPI + uvicorn for the API layer (SSE streaming per DECISIONS.md D7)
- LangGraph + langchain-core for the agent graph; Pydantic v2 for all schemas
- LLM access ONLY through `app/llm/client.py` factory — model, base URL, and API key come
  from environment (`LLM_MODEL`, `OPENCODE_BASE_URL`, `OPENCODE_API_KEY`). Never hard-code
  model names or keys. A mock mode (`LLM_MODE=mock`) must let the whole pipeline run with no
  API key.
- Structured outputs: every LLM call returns a Pydantic model via
  `with_structured_output`; validate, on failure retry once feeding the validation error
  back, then surface a clean error (see DECISIONS.md D8).
- Ranking is a pure Python function (D3) — LLM produces weights, never the order. Keep the
  scorer side-effect free and unit-tested.

## Target layout (Phase 1)

```
backend/
  pyproject.toml
  app/
    main.py            # FastAPI app, /health, /api/chat (SSE)
    config.py          # env-driven settings
    llm/client.py      # LLM factory + mock mode + retry wrapper
    catalog/           # product models, ~28-item curated dataset, loader
    tools/             # search_products, get_product_specs, get_product_reviews, cart ops
    graph/             # LangGraph: intent → clarify_gate → search → research → recommend → ui_plan → respond
    dsl/               # UI plan Pydantic schemas + validation
    api/               # SSE endpoint, protocol event models
  tests/               # pytest: scorer, tools, dsl validation, graph happy path (mock mode)
```

## Quality gates (all must pass before any PR)

```
cd backend && uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Rules

- Conventional Commits; small focused PRs.
- Never commit `.env` or any API key.
- Do not touch `frontend/` (doesn't exist yet), `PRD.md`, or `DECISIONS.md` without the
  owner's explicit instruction.
- Determinism: temp 0 everywhere; identical input must produce identical ranking.
