<!--
Conventional Commits title format: `type: short imperative summary`
Types: feat | fix | docs | chore | refactor | test | perf | ci
The pre-commit hook (ruff + hygiene) runs automatically on this PR.
-->

## What

<!-- 1–3 sentences: what this PR does and why. Link the driving spec/issue. -->

## Why

<!-- The problem or the spec decision driving this. Reference DECISIONS.md D-numbers or specs/<feature>/ where applicable. -->

## Changes

<!-- Bullet list of the meaningful changes (files/modules), newest context first. -->

-

## How Was It Tested

<!-- Check the gates you ran (AGENTS.md quality gates are mandatory): -->

- [ ] `cd backend && uv sync`
- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run pytest`
- [ ] Manual validation (describe): <!-- e.g. quickstart.md steps, curl SSE checks -->

## Constitution / Decisions Check

<!-- Every PR must comply with .specify/memory/constitution.md and DECISIONS.md. -->

- [ ] No violation of locked decisions (D1–D8); LLM access only via `app/llm/client.py`
- [ ] Ranking stays deterministic (pure scorer, temp 0, identical input → identical order)
- [ ] No secrets committed; env-only configuration
- [ ] Phase discipline respected (no `frontend/` changes; `PRD.md`/`DECISIONS.md` untouched)

## Checklist

- [ ] Conventional Commit title
- [ ] Small, focused diff (split if unrelated changes creep in)
- [ ] Docs/specs updated (`specs/`, `AGENTS.md`) if behavior or architecture changed
- [ ] V2 backlog not silently implemented (see DECISIONS.md deferrals)
