<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0 (initial ratification)
Modified principles: (none — initial adoption)
Added sections:
  - Core Principles I–VIII
  - Constraints & Security
  - Development Workflow & Quality Gates
  - Governance
Removed sections: (none)
Follow-up TODOs: (none)
Source of principles: DECISIONS.md v1.0 (locked 2026-08-29) + AGENTS.md crew guide.
-->

# Agentic-Shop Constitution

## Core Principles

### I. Decisions Record Is Binding

`DECISIONS.md` is the single architecture authority. Where the PRD and
`DECISIONS.md` disagree, `DECISIONS.md` wins. Any code, spec, or plan that
deviates from a decision marked ✅ MUST be treated as a violation until
`DECISIONS.md` is formally amended (see Governance). Rationale: the record
exists to prevent re-litigating settled architecture during implementation.

### II. LLM Access Behind the Factory

All model access MUST go through `app/llm/client.py`. Model name, base URL,
and API key come exclusively from environment (`LLM_MODEL`,
`OPENCODE_BASE_URL`, `OPENCODE_API_KEY`); hard-coding any of them is
forbidden. A mock mode (`LLM_MODE=mock`) MUST let the entire pipeline run
with no API key and no external service. Rationale: the model is a swappable
dependency, and CI/demos must never require paid network calls.

### III. Deterministic Core, Narrative Edge

Ranking MUST be a pure Python function (`score = Σ(weight_i ×
normalized_attr_i)`) that is side-effect free and unit-tested. The LLM MAY
produce preference weights and MAY narrate results, but MUST never decide
order. Temperature MUST be 0 for every call. Identical input MUST produce a
byte-identical ranking. Rationale: an LLM-computed order is untestable and
unreproducible; the numeric core is the product's trust anchor.

### IV. Structured Outputs or No Outputs

Every LLM call MUST request a Pydantic model via `with_structured_output`.
On validation failure the system MUST retry exactly once, feeding the
validation error back to the model; a second failure MUST surface a clean
`error` event to the client — never raw model output, never a silent
fallback. Rationale: open-weight gateway models are flaky; the wrapper
(D8) is the resilience boundary.

### V. Contract-First UI DSL

The agent emits UI as validated, structured plan documents — never as
executable frontend code. Each turn emits exactly ONE full plan that
replaces the previous turn's plan (no patching in MVP). The plan schemas
are the frontend contract: Pydantic (backend) and Zod (frontend) MUST both
validate the same `fixtures/ui-plans/*.json`. Rationale: a validated DSL
with a shared fixture corpus is what makes agent-generated UI safe and
testable on both sides.

### VI. Phase Discipline

Work happens in the phase the owner declares (currently Phase 1 — backend
scaffold only). `frontend/`, `PRD.md`, and `DECISIONS.md` MUST NOT be
created or modified without the owner's explicit instruction. Rationale:
the frontend lands on an owner-supplied Next.js boilerplate; premature
scaffolding would be discarded.

### VII. Quality Gates Before Any PR

Every change MUST pass, before review: `uv sync`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run pytest` (from `backend/`). Tests
are required, not optional: the scorer, tools, DSL validation, and the
graph happy path (mock mode) MUST have automated coverage. Rationale:
the pipeline's value claim is "deterministic and testable"; unverified
code breaks that claim.

### VIII. Simplicity and Deferred Complexity

The graph MUST be the fixed backbone `intent → clarify_gate → search →
research → recommend → ui_plan → respond` with exactly one conditional
edge (the deterministic clarify gate). Free routing, dynamic supervisors,
plan patching, extra components, and real commerce integrations are V2 and
MUST NOT be built "while we're in there". Rationale: YAGNI is the only
defense against an agent system accreting untestable magic.

## Constraints & Security

- Secrets: `.env` and any API key MUST NEVER be committed. Configuration is
  environment-driven; no credentials in code, fixtures, or tests.
- Scope: no real payments, checkout, inventory, shipping, or product
  ingestion. The catalog is a curated ~28-item JSON dataset of headphones
  with pre-scored reviews (D5); the research agent reads scores/quotes and
  MUST NOT perform runtime NLP extraction.
- State: session state uses an in-memory checkpointer (`MemorySaver`,
  `thread_id` = session id). Persistence across process restarts is out of
  MVP scope.
- Transport: plain FastAPI `StreamingResponse` over SSE with the exact
  lifecycle events in D7 (`status`, `message_delta`, `ui_update`,
  `turn_end`, `error`). No websockets in MVP.
- Determinism: temperature 0 everywhere; no wall-clock, randomness, or
  network order effects inside ranking or clarify decisions.

## Development Workflow & Quality Gates

- Branching: small focused PRs; Conventional Commits (`feat:`, `chore:`,
  `docs:`, `fix:`, `test:`).
- Dependencies: backend deps managed exclusively with `uv` (`uv add`,
  `uv run`); Python 3.12. Frontend (future): pnpm.
- Stack (locked, D8): FastAPI + uvicorn, LangGraph + langchain-core,
  Pydantic v2, LLM via OpenCode gateway (OpenAI-compatible), Tailwind +
  shadcn/ui (frontend phase), zustand (frontend phase).
- Every feature plan MUST include a Constitution Check section validating
  compliance with principles I–VIII; violations must be justified in the
  plan or removed.
- Spec-driven flow: new feature work starts with `$speckit-specify` and
  passes `$speckit-clarify`/`$speckit-plan`/`$speckit-tasks` before
  `$speckit-implement`.

## Governance

- This constitution supersedes all other practices, prompts, and agent
  habits in this repository. Conflict ⇒ constitution wins; perceived
  conflict with `DECISIONS.md` ⇒ they must be reconciled, since the
  constitution is derived from it.
- Amendments: propose in a PR that updates this file plus, when the change
  alters architecture, a corresponding `DECISIONS.md` entry. Version bumps
  follow semver: MAJOR for principle removals/redefinitions, MINOR for new
  principles or materially expanded guidance, PATCH for clarifications.
- Compliance review: `$speckit-plan` Constitution Check gates every feature;
  reviewers MUST verify the quality gates of Principle VII ran green.
- Runtime development guidance lives in `AGENTS.md`; it MUST stay
  consistent with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
