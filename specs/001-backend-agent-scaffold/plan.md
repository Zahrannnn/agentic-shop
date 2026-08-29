# Implementation Plan: Agentic Shopping Backend (Phase 1 Scaffold)

**Branch**: `001-backend-agent-scaffold` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-backend-agent-scaffold/spec.md`

**Note**: This template is filled in by the `$speckit-plan` command; its definition describes the execution workflow.

## Summary

Build the Phase 1 backend: a Python 3.12 / FastAPI service exposing a streaming
chat endpoint that runs a fixed LangGraph workflow (intent → clarify_gate →
search → research → recommend → ui_plan → respond) over a curated ~28-item
headphone catalog. Every turn streams D7 lifecycle events and ends with one
validated UI plan document (Pydantic DSL, fixture-backed contract). Ranking is a
pure deterministic scorer fed by LLM-derived weights; all model access goes
through one env-configured factory with a keyless mock mode and a
validate-retry-once wrapper. Deliverables: catalog + tools, agent graph, DSL
schemas, SSE API, and the full pytest/ruff quality-gate suite.

## Technical Context

**Language/Version**: Python 3.12 (managed/locked by AGENTS.md)

**Primary Dependencies**: FastAPI, uvicorn, LangGraph, langchain-core,
langchain-openai (OpenAI-compatible gateway client), Pydantic v2 +
pydantic-settings, ruff (lint+format), pytest (+ pytest-asyncio, httpx for
ASGI-level endpoint tests)

**Storage**: None — curated JSON catalog file loaded at startup; per-session
state held in-memory via LangGraph `MemorySaver` (`thread_id` = session id)

**Testing**: pytest — unit (scorer, clarify rules, DSL validation), contract
(SSE event sequence, UI plan fixtures), integration (graph happy path in mock
mode via httpx ASGI transport; no live server, no network)

**Target Platform**: Local development server (uvicorn); developer machines
(Windows/macOS/Linux), CI-friendly — zero network and zero credentials required

**Project Type**: web-service (single backend API; frontend is a later phase on
an owner-supplied boilerplate)

**Performance Goals**: Full mock-mode turn (lifecycle events → answer → plan →
end) completes in < 5 s (SC-001); catalog load + score of the full catalog is
trivially fast (pure in-memory computation over ~28 items)

**Constraints**: temperature 0 on every model call; identical input → identical
ranking (FR-015); no secrets in repo (env-only config); SSE event order is
fixed by D7; no websockets; no UI plan patching (D2 full replace); backend-only
scope — no frontend files (constitution principle VI)

**Scale/Scope**: ~28 catalog items, 5 user stories, 1 service, MVP registry of
6–8 DSL component types; sessions are single-user local (no auth)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Compliance | Status |
|---|-----------|------------|--------|
| I | Decisions Record Is Binding | Plan implements D1–D8 verbatim: transcript surface, full-replace plans, deterministic scorer, rule-based clarify gate, curated catalog, fixed graph + one conditional edge, SSE lifecycle, locked stack | ✅ PASS |
| II | LLM Access Behind the Factory | Single `app/llm/client.py` factory; `LLM_MODEL`/`OPENCODE_BASE_URL`/`OPENCODE_API_KEY`/`LLM_MODE` from env via pydantic-settings; mock mode requires no key | ✅ PASS |
| III | Deterministic Core, Narrative Edge | `recommend` node calls a pure `score_products()` function; LLM emits weights only (structured output); temperature=0 asserted in client factory; determinism unit tests planned (SC-002) | ✅ PASS |
| IV | Structured Outputs or No Outputs | All nodes use `with_structured_output(PydanticModel)`; shared retry wrapper: validate → retry once with validation error → emit clean `error` event | ✅ PASS |
| V | Contract-First UI DSL | `app/dsl/` Pydantic schemas; `fixtures/ui-plans/*.json` created in this phase as the shared contract corpus; validation before `ui_update` emission | ✅ PASS |
| VI | Phase Discipline | Backend files only (`backend/`, `specs/`, `fixtures/`); no `frontend/`, no edits to `PRD.md`/`DECISIONS.md` | ✅ PASS |
| VII | Quality Gates Before Any PR | Tasks include ruff check/format, pytest suite covering scorer, tools, DSL validation, graph happy path; gates run in quickstart.md | ✅ PASS |
| VIII | Simplicity and Deferred Complexity | Graph is the fixed 7-node backbone with exactly one conditional edge; no plan patching, no dynamic routing, no extra components; V2 list respected | ✅ PASS |

**Post-design re-check**: data model and contracts (Phase 1 artifacts below)
stay within D1–D8 and principles I–VIII — no violations introduced. Notably:
the contracts folder documents only the two locked interfaces (HTTP/SSE and the
UI DSL), the state model uses the in-memory checkpointer only, and no V2
capability (patching, routing, extra components) leaked into the design.

## Project Structure

### Documentation (this feature)

```text
specs/001-backend-agent-scaffold/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
│   ├── http-api.md      #   REST + SSE endpoint contract
│   └── ui-dsl.md        #   UI plan DSL contract + fixture corpus
├── checklists/
│   └── requirements.md  # Spec quality checklist ($speckit-specify output)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml            # uv-managed project: deps, ruff config, pytest config
├── .env.example              # documents LLM_MODEL / OPENCODE_* / LLM_MODE (no real secrets)
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app factory; mounts routes; /health
│   ├── config.py             # pydantic-settings: env-driven Settings
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py         # get_llm() factory (real | mock), temperature=0, retry-once structured wrapper
│   ├── catalog/
│   │   ├── __init__.py
│   │   ├── models.py         # Product, ReviewScores Pydantic models
│   │   ├── data/headphones.json   # curated ~28-item dataset (4 flights winners)
│   │   └── loader.py         # load + validate catalog; attribute normalization helpers
│   ├── ranking/
│   │   ├── __init__.py
│   │   └── scorer.py         # PURE score_products(candidates, weights) -> list[ScoredProduct]
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py         # search_products(category, max_price, attributes)
│   │   ├── research.py       # get_product_specs, get_product_reviews (pre-scored)
│   │   └── cart.py           # add_to_cart, remove_from_cart, get_cart (per-session mock cart)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py          # ShoppingState TypedDict
│   │   ├── schemas.py        # per-node structured output models
│   │   ├── nodes.py          # intent, clarify_gate (pure rules), search, research, recommend, ui_plan, respond
│   │   └── builder.py        # build_graph(): fixed backbone, MemorySaver checkpointer
│   ├── dsl/
│   │   ├── __init__.py
│   │   ├── models.py         # UIPlan, ComponentNode, UIAction Pydantic schemas
│   │   └── validate.py       # plan validation + serialization; fixture round-trip helpers
│   └── api/
│       ├── __init__.py
│       ├── schemas.py        # ChatRequest, protocol event models
│       └── routes.py         # GET /health, POST /api/chat -> SSE StreamingResponse
├── fixtures/
│   └── ui-plans/*.json       # shared contract corpus (source of truth for DSL)
└── tests/
    ├── conftest.py           # mock-mode fixtures, httpx ASGI client, fake-LLM fault injection
    ├── test_scorer.py        # pure scorer: ordering, normalization, budget, missing attrs
    ├── test_clarify_gate.py  # rule table: ask once, budget assumption, contradictions
    ├── test_tools.py         # search/research/cart behavior
    ├── test_dsl.py           # plan validation: valid fixtures pass, mutations fail
    ├── test_api_sse.py       # event order contract + busy handling
    └── test_graph_happy_path.py  # full mock-mode turns: US1–US5 acceptance scenarios
```

**Structure Decision**: Single backend service exactly as laid out in AGENTS.md
"Target layout (Phase 1)", extended with two additions the constitution
requires: `app/ranking/scorer.py` (the pure scoring function gets its own
side-effect-free module per principle III) and `backend/fixtures/ui-plans/`
(the shared DSL contract corpus per principle V and DECISIONS.md D8 open item
4). The `dsl/`, `graph/`, `tools/`, `catalog/`, `api/`, `llm/` packages map 1:1
to the AGENTS.md target layout.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty.
