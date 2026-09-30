<h1 align="center">agentic-shop</h1>

<p align="center">
  <a href="#quickstart"><img alt="python" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white&style=flat-square"></a>
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white&style=flat-square">
  <img alt="Pydantic v2" src="https://img.shields.io/badge/Pydantic%20v2-E92063?logo=pydantic&logoColor=white&style=flat-square">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js%2016-000000?logo=next.js&logoColor=white&style=flat-square">
  <img alt="React 19" src="https://img.shields.io/badge/React%2019-61DAFB?logo=react&logoColor=black&style=flat-square">
  <img alt="A2UI" src="https://img.shields.io/badge/A2UI%20v0.9-projection-4285F4?style=flat-square">
  <img alt="tests" src="https://img.shields.io/badge/tests-504%20passing-3DDC84?style=flat-square">
  <a href="https://github.com/Zahrannnn/agentic-shop/pull/1"><img alt="phase 1" src="https://img.shields.io/badge/phase%201-backend-8A2BE2?style=flat-square"></a>
  <a href="https://github.com/Zahrannnn/agentic-shop/pull/4"><img alt="phase 2" src="https://img.shields.io/badge/phase%202-frontend-FF6F61?style=flat-square"></a>
</p>

<p align="center"><em>"The UI is an output of the agent, not the place where the agent operates."</em></p>

This is my first practice project for Agentic Frontend: a shopping experience where
you skip the catalog pages entirely and just tell an agent what you need. Say
*"headphones for long flights under $200, noise cancellation matters"* and a LangGraph
pipeline searches a curated catalog, ranks products with a deterministic scorer, and
streams back an answer plus a validated UI plan that the client renders as grids,
comparisons, and cart views.

The second act is where it got interesting. A judgment layer (TypeSafe Jev) grades
your stated priorities on typed rubrics before they become ranking weights. Every
turn is also projected onto Google's A2UI v0.9 protocol and rendered side by side
with the native stack. The plan registry grew real interactivity: refine chips on
grids, quantity steppers on carts, a multi-select "what matters to you" ask. And
cart taps stopped waiting for the agent — a direct `PATCH /api/cart` mutates the
checkpoint and the table updates in the same frame, no streamed turn, no spinner.

I built it to learn the agentic frontend patterns end to end: planning with GitHub
Spec Kit, a Python/LangGraph backend, a Next.js renderer, and the contract between
them. Every feature went through a spec → plan → tasks → implement cycle, and both
suites (504 tests) run offline in mock mode.

> [!TIP]
> Everything runs **keyless and offline** in mock mode: the full agent pipeline,
> the judgment layer, the A2UI projection, the SSE API, the frontend, and the whole
> test suite. Drop in a real model (Z.ai coding plan, OpenCode Zen, any
> OpenAI-compatible gateway) when you want it live.

**Explore:** [Quickstart](#quickstart) · [Architecture](#how-it-works) · [System design](#system-design) · [Try the MVP scenario](#try-the-mvp-scenario) · [Design system](#design-system) · [Real model](#use-a-real-model)

---

## The app

| | |
|---|---|
| ![The storefront](docs/screenshots/shop-empty.png) | ![Recommendation turn](docs/screenshots/shop-recommendation.png) |
| The storefront: light "Curator's Desk" surface, suggestion chips, renderer toggle, REAL/MOCK badge | Recommendation turn: streamed answer, ranked cards, and refine chips that re-sort the field without a new question |
| ![Comparison](docs/screenshots/shop-compare.png) | ![Details](docs/screenshots/shop-details.png) |
| Comparison arena: spec scoreboard with best-cell highlights, values straight from the catalog | Details evidence card: reviewer score meters you can hover to reveal the exact quotes behind them |
| ![Cart](docs/screenshots/shop-cart.png) | ![Catalog sheet](docs/screenshots/shop-catalog-sheet.png) |
| Cart view: quantity steppers patch the checkpoint directly — counts and total update instantly | Catalog sheet: browse all 38 products, one tap asks the agent |

Full-width layout, sticky composer, a live stage trail while the model works
(*searching → 38 candidates → researching → ranking → building UI*), and a
REAL/MOCK mode badge. The transcript is the only navigation.

> [!TIP]
> Building a frontend against this? **[FRONTEND_GUIDE.md](FRONTEND_GUIDE.md)** is the
> agent-ready contract: endpoints, SSE state machine, plan registry, and a
> definition of done. No backend code reading required.

---

## How it works

```mermaid
flowchart LR
    U["🛍️ Shopper"] -->|"natural language"| API["POST /api/chat<br/>SSE stream"]
    U -->|"widget taps"| PATCH["PATCH /api/cart<br/>no turn, no model"]
    PATCH -.->|"read · mutate<br/>checkpoint"| G
    API --> G

    subgraph G["LangGraph pipeline (thread_id = session)"]
        direction LR
        I["intent<br/>(+ Jev grades)"] --> CG{"clarify_gate<br/>(rule-based)"}
        CG -->|"ask"| QA["ui_agent_ask"]
        CG -->|"priorities"| QP["ui_agent_ask_priorities"]
        CG -->|"proceed"| S["search"] --> RES["research"] --> REC["recommend"] --> UP["ui_plan"] --> R["respond"]
    end

    S -.->|"filter"| C[("curated catalog<br/>38 products")]
    REC -.->|"weights → score"| P["pure scorer<br/>Σ weightᵢ × attrᵢ"]
    UP -.->|"validate"| D["UI plan DSL<br/>registry v1.1"]
    UP -.->|"project"| A["A2UI v0.9<br/>messages"]
    RES -->|"narrate"| LLM["LLM behind factory<br/>(env-configured · mock mode)"]

    API -->|"status · message_delta · ui_update ·<br/>a2ui_update · turn_end"| U
    PATCH -->|"re-rendered plan"| U
```

A few decisions I care about here:

**The LLM never decides order.** It maps your stated priorities to attribute weights;
a pure, unit-tested scorer computes the ranking. Same input, same ranking, every time
(byte-identical in mock mode). With the judgment layer on (`JEV_MODE=real`), those
priorities are first graded on typed 0–10 rubrics by TypeSafe Jev — calibrated
probabilities, not free-text vibes — and a low-confidence category choice falls back
to the rule-based clarify gate.

**Plans are data, not code.** Every turn ends with one validated UI plan document.
The registry is at 7 component types and 9 action kinds; the backend rejects unknown
component types, foreign product ids, out-of-bounds lists, and malformed action
payloads before anything reaches the wire, so the client never renders a broken plan.

**The same plan speaks two protocols.** Every validated plan is additionally
transpiled to A2UI v0.9 messages and streamed as an optional `a2ui_update` frame
(clients that don't know A2UI just ignore it). A header toggle renders both stacks
side by side; the native plan stays the source of truth.

**The cart doesn't wait for the agent.** Stepper taps go straight to
`PATCH /api/cart`, which mutates the LangGraph checkpoint and returns the
authoritative re-rendered plan. The client applies the change optimistically and
reverts if the patch fails — conversational edits like *"set the second one to 3"*
still ride the full pipeline.

**Failures degrade on contract.** Schema failures retry once with the validation error
fed back to the model, then a single clean `error` event ends the turn. You never see
raw model output.

The clarify gate is a rule table, not a model judgment: unknown category gets one chip
question (never twice in a row), abstract priorities get a multi-select ask
(*"which of these matter: noise cancellation, comfort, battery…?"*), a missing budget
proceeds with a stated $250 cap, and impossible constraints get the closest matches
with the trade-off honestly flagged.

## Quickstart

Backend needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Frontend needs
Node 22 and npm. No API key needed for mock mode.

```bash
git clone https://github.com/Zahrannnn/agentic-shop && cd agentic-shop

# backend: agent pipeline + SSE API (291 tests, fully offline)
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --reload   # LLM_MODE=mock is the default

# frontend: transcript UI + plan renderer (213 tests)
cd ../frontend
npm install
npm run verify                         # lint + typecheck + vitest + build
npm run dev                            # http://localhost:3000/shop
```

CORS is pre-wired for the Next.js dev ports, and the shop page shows a MOCK/REAL
badge from the backend's `/health` (which also reports the judgment-layer mode).

> [!NOTE]
> Longer walkthroughs: [backend quickstart](specs/001-backend-agent-scaffold/quickstart.md)
> and [frontend quickstart](specs/002-frontend-ui-renderer/quickstart.md).

## Try the MVP scenario

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-12345","message":"Help me find the best headphones for long flights under $200. Noise cancellation and comfort matter most."}'
```

```text
event: status        data: {"stage":"intent_parsed"}
...
event: message_delta data: {"text":"Aurora Hush Pro ($179): adaptive ANC rated 4.9/5..."}
...
event: ui_update     data: {"planVersion":"1","root":{"type":"product_grid",...}}
event: a2ui_update   data: {"messages":[{"version":"v0.9",...}]}
event: turn_end      data: {}
```

Then, in the same session: *"compare the first two"* gives you a comparison table,
*"add the first one to my cart"* gives you a cart view, the refine chips re-run the
search inside the same turn's anchor, and the steppers go through the direct path:

```bash
curl -X PATCH http://127.0.0.1:8000/api/cart \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-12345","product_id":"aurora-hush-pro","quantity":3}'
```

No streamed turn, no model call — just the mutated checkpoint and the re-rendered
cart. The whole search → refine → compare → recommend → cart loop stays inside the
transcript. Prefer clicking? `npm run dev` in `frontend/`, open
`http://localhost:3000/shop`, and run the same scenario with the suggestion chips.

## Design system

The frontend follows a small written doctrine, "The Curator's Desk", captured in
[PRODUCT.md](PRODUCT.md) (voice, users, anti-references) and [DESIGN.md](DESIGN.md)
(OKLCH tokens, type scale, named rules like *The One Underline Rule* and *The Paper
Rule*). Implementation lives in `frontend/src/app/globals.css`: warm cream neutrals,
a single coral accent spent only where the agent commits, hairline borders over
shadows, Space Grotesk + IBM Plex Mono. The anti-slop bans are written down and
enforced: no purple-blue gradients, no glass cards, no side-stripe borders, no
hero-metric template.

## Use a real model

All model access is env-configured behind `backend/app/llm/client.py`, so swapping
models is a `.env` change. Two transports ship: any OpenAI-compatible gateway
(`LLM_SDK=openai`, the default) and Z.ai's official SDK (`LLM_SDK=zai`, structured
output pinned to function calling). What I actually run it on — a Z.ai coding plan:

```bash
LLM_MODE=real
LLM_SDK=zai
LLM_MODEL=glm-5.3-flash
OPENCODE_BASE_URL=https://api.z.ai/api/coding/paas/v4
OPENCODE_API_KEY=<your-key>
```

A free OpenCode Zen example:

```bash
LLM_MODE=real
LLM_SDK=openai
LLM_MODEL=muse-spark-1.2-contributor-free
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_KEY=<your-key>
LLM_API_STYLE=responses        # muse is a Responses-API-only reasoning model
```

The judgment layer has its own switch and its own key, off by default:

```bash
JEV_MODE=real                  # off | mock | real
JEV_API_KEY=<your-typesafe-key>
```

> [!IMPORTANT]
> Never commit `.env` or any key. The structured-output wrapper falls back to
> schema-in-prompt JSON mode for models that reject strict schemas, and the Z.ai
> transport pins function calling — swapping providers stays a config change.

## Project structure

```text
├── PRD.md                             product requirements (v0.1 MVP)
├── DECISIONS.md                       locked architecture decisions (binding, D1–D12)
├── AGENTS.md                          crew guide for coding agents
├── PRODUCT.md / DESIGN.md             design context (Curator's Desk system)
├── FRONTEND_GUIDE.md                  agent-ready backend contract for FE implementers
├── specs/001-backend-agent-scaffold/  backend spec · research · plan · contracts · tasks
├── specs/002-frontend-ui-renderer/    frontend spec · research · plan · data-model · tasks
├── specs/003-jev-and-a2ui/            judgment layer + A2UI projection (D9–D10)
├── specs/004-interactive-registry/    registry v1.1: refine bar, steppers, multi-picker (D11)
├── specs/005-optimistic-cart/         PATCH /api/cart + instant client updates (D12)
├── docs/screenshots/                  the app in action (light Curator's Desk)
├── .specify/                          GitHub Spec Kit (constitution, templates)
├── backend/                           detailed guide: backend/README.md
│   ├── app/llm/          model factory · Z.ai SDK transport · Jev judgment client · mocks
│   ├── app/catalog/      curated dataset · Pydantic models · loader
│   ├── app/ranking/      the pure deterministic scorer
│   ├── app/tools/        search · pre-scored research · mock cart
│   ├── app/graph/        state · nodes · followups · builder (MemorySaver)
│   ├── app/dsl/          UI plan registry v1.1 · payload validation
│   ├── app/a2ui/         plan → A2UI v0.9 transpiler + golden fixtures
│   ├── app/api/          /health · /api/chat (SSE) · PATCH /api/cart
│   ├── fixtures/         shared plan corpus + A2UI goldens
│   └── tests/            291 tests: scorer, tools, DSL, A2UI, SSE contract, graph, cart API
└── frontend/            detailed guide: frontend/README.md (Next.js 16 · React 19 · Tailwind v4)
    ├── src/features/shopping/   the whole feature: api/ (SSE client, frame parser),
    │                            hooks/ (use-agent-turn: streaming + optimistic patch),
    │                            store/ (RTK slices), validations/ (Zod mirrors of the
    │                            plan DSL + A2UI wire), components/ (renderer registry
    │                            + transcript UI)
    ├── src/components/ui/       shadcn primitives (theme = Curator's Desk tokens)
    ├── src/shared/              env config · store composition · providers
    └── ...                      vitest setup, husky, Docker/CI infra
```

## Development

**Backend** (`cd backend`):

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

**Frontend** (`cd frontend`):

```bash
npm install
npm run verify        # eslint + tsc --noEmit + vitest + next build
```

- **Hooks**: root `uv tool install pre-commit && pre-commit install` (ruff + hygiene);
  `frontend/` ships its own husky + lint-staged via `npm install`.
- **Flow**: feature work goes through Spec Kit (`$speckit-specify` → plan → tasks →
  implement); every plan is gated against the project constitution
  (`.specify/memory/constitution.md`).
- **Design**: frontend work follows `PRODUCT.md` + `DESIGN.md` (warm cream palette,
  one coral accent, editorial type, the named anti-slop bans).
- **Commits**: Conventional Commits, small focused PRs (PR template included).
- **Next up**: more judgment-layer targets (clarify-gate decisions, follow-up
  disambiguation), more catalog categories, richer comparison state, and eventually
  real product APIs. The full deferred list lives in `DECISIONS.md`.
