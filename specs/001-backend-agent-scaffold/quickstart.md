# Quickstart — Validate the Agentic Shopping Backend

**Feature**: `001-backend-agent-scaffold`

Runnable proof that the feature works end-to-end, without credentials and
without touching the network. Full scenario detail lives in
[spec.md](./spec.md); interface detail lives in [contracts/](./contracts/).

## Prerequisites

- Python 3.12 + [`uv`](https://docs.astral.sh/uv/) on PATH
- No `.env` required — everything below runs in mock mode (`LLM_MODE=mock` is
  the default)

## 1. Install and run quality gates (SC-006)

```bash
cd backend
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest            # scorer, clarify rules, tools, DSL fixtures, SSE contract, graph happy path
```

Expected: all green on a machine with no API key and no network.

## 2. Start the server (mock mode)

```bash
uv run uvicorn app.main:app --reload
```

Liveness:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","mode":"mock"}
```

## 3. Run the MVP scenario turn (US1 + US3)

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-1","message":"Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most."}'
```

Expected SSE sequence (see [contracts/http-api.md](./contracts/http-api.md)):

1. `status` frames in stage order `intent_parsed → searching → found_n →
   researching → ranking → building_ui`
2. `message_delta` frames assembling a short answer
3. one `ui_update` whose plan validates against
   [contracts/ui-dsl.md](./contracts/ui-dsl.md) and matches the
   `product-grid-flights` fixture semantically
4. `turn_end`

The recommended top-3 must not exceed $200, and the #1 product must be the
battery/ANC/comfort/value trade-off winner consistent with the stated
priorities.

## 4. Clarify path (US2)

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-2","message":"Help me pick a gift"}'
```

Expected: `intent_parsed` → one `message_delta` question → `ui_update` with a
`preference_picker` → `turn_end`. Then answer and confirm run-to-completion
(no second question).

## 5. Multi-turn follow-ups in one session (US4)

Repeat with the same `session_id`:

1. `"compare the first two"` → `comparison_table` plan with exactly the first
   two ranked ids.
2. `"I care more about comfort than sound quality"` → re-ranked grid;
   explanation mentions the change.
3. `"add the first one to my cart"` → `cart_view` plan; then
   `"what's in my cart?"` → same cart contents.

## 6. Determinism check (US5, SC-002)

Run step 3 twice with fresh session ids in two terminals; the ranked
`productIds` in both `ui_update` frames must be identical item-for-item and
order-for-order.

## 7. Fault injection (US5, SC-007) — automated only

Covered by `tests/test_graph_happy_path.py` via the scripted fake LLM:
malformed structured output → exactly one retry → single `error` frame
(`code=structured_output`), no raw model text reaches the client. Run:

```bash
uv run pytest tests/test_graph_happy_path.py -k fault
```

## 8. Busy guard (FR-016) — automated only

Covered by `tests/test_api_sse.py`: a second concurrent `POST /api/chat` for
the same `session_id` mid-turn receives `409 {"detail":"turn_in_flight"}`.

## Where to look when something fails

| Symptom | First place to check |
|---|---|
| Gates fail on formatting/lint | `backend/pyproject.toml` ruff config vs code style |
| SSE order broken | `app/graph/nodes.py` writers vs `app/api/routes.py` framing |
| Plan rejected | `app/dsl/validate.py` vs `backend/fixtures/ui-plans/` |
| Ranking not reproducible | `app/ranking/scorer.py` (tie-break, normalization) |
| Mock mode missing | `app/config.py` (`LLM_MODE` default) + `app/llm/client.py` |
