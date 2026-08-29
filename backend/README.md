# agentic-shop backend

Phase 1 backend for the agentic shopping system: a LangGraph agent pipeline that
answers shopping requests over a curated headphone catalog and streams results
as UI plan documents (SSE). Architecture is locked in `../DECISIONS.md`; the
feature spec lives in `../specs/001-backend-agent-scaffold/`.

## Run it (no API key needed)

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Mock mode (`LLM_MODE=mock`) is the default — the whole pipeline runs offline.

Try it:

```bash
curl http://127.0.0.1:8000/health
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","message":"Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most."}'
```

You get a stream of `status` → `message_delta` → `ui_update` (a validated UI
plan document) → `turn_end` events.

## Quality gates (required before any PR)

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Full validation scenarios: [`../specs/001-backend-agent-scaffold/quickstart.md`](../specs/001-backend-agent-scaffold/quickstart.md).

## Configuration

Copy `.env.example` to `.env` and set `LLM_MODE=real` with `LLM_MODEL`,
`OPENCODE_BASE_URL`, and `OPENCODE_API_KEY` to use the OpenCode gateway. Never
commit `.env`.
