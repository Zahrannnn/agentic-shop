# agentic-shop backend

The LangGraph agent pipeline for the agentic shopping system: it answers shopping
requests over a curated catalog (headphones + earbuds), ranks products with a
deterministic scorer, and streams conversational answers plus **validated UI plan
documents** as server-sent events. Architecture is locked in `../DECISIONS.md`; the
feature spec lives in `../specs/001-backend-agent-scaffold/`.

## Architecture

```text
POST /api/chat ──▶ LangGraph pipeline (thread_id = session)
                   intent → clarify_gate ─(ask)→ ui_agent_ask ─▶ END
                                └─(proceed)→ search → research → recommend
                                           → ui_plan → respond ─▶ END
SSE back: status … → message_delta → ui_update (validated plan) → turn_end
```

| Module | Role |
|---|---|
| `app/llm/` | The only doorway to any model: env-configured `ChatOpenAI` (OpenCode Zen gateway), deterministic `MockChatLLM`, validate → retry-once → fail-clean structured-output wrapper |
| `app/catalog/` | Curated dataset (28 headphones + 10 earbuds with pre-scored reviews) · Pydantic models · loud-fail loader + normalization |
| `app/ranking/` | Pure deterministic scorer — the LLM proposes weights, never order; identical input ⇒ identical ranking |
| `app/tools/` | search (with deterministic relaxation) · pre-scored research · mock cart |
| `app/graph/` | `ShoppingState`, nodes, `followups` resolver, builder (fixed backbone + MemorySaver) |
| `app/dsl/` | UI plan schemas + catalog-aware validation (camelCase wire format) |
| `app/api/` | `/health` · `/api/catalog` · `POST /api/chat` (SSE lifecycle, 409/404 guards) |

Contracts: [`../specs/001-backend-agent-scaffold/contracts/`](../specs/001-backend-agent-scaffold/contracts/)
(HTTP+SSE protocol and the UI plan DSL). Plan fixtures:
[`fixtures/ui-plans/`](fixtures/ui-plans/).

## Run it (no API key needed)

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Mock mode (`LLM_MODE=mock`) is the default — the whole pipeline runs offline, and
the shop page shows a `MOCK` badge.

Try it:

```bash
curl http://127.0.0.1:8000/health
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","message":"Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most."}'
```

You get a stream of `status` → `message_delta` → `ui_update` (a validated UI
plan document) → `turn_end` events. Other endpoints: `GET /api/catalog` (browse
feed) and `GET /health`.

## Quality gates (required before any PR)

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Full validation scenarios: [`../specs/001-backend-agent-scaffold/quickstart.md`](../specs/001-backend-agent-scaffold/quickstart.md).

## Configuration

Copy `.env.example` to `.env` and set `LLM_MODE=real` with `LLM_MODEL`,
`OPENCODE_BASE_URL`, and `OPENCODE_API_KEY` to use the OpenCode gateway
(`LLM_API_STYLE=responses` for Responses-API-only models like muse). Never
commit `.env`. CORS origins for browser clients: `ALLOWED_ORIGINS`
(comma-separated; the Next.js dev ports are pre-allowed).
