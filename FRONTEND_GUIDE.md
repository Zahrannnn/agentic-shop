# FRONTEND_GUIDE.md — implement the agentic-shop frontend against this backend

**Audience:** a frontend developer or a coding agent implementing the Phase 2 UI.
This file is self-sufficient: you should **not** need to read backend code. The two
authoritative machine-readable contracts are:

- `specs/001-backend-agent-scaffold/contracts/http-api.md` — endpoint + SSE protocol
- `specs/001-backend-agent-scaffold/contracts/ui-dsl.md` — the UI plan document schema

Interactive API docs: run the backend and open `http://127.0.0.1:8000/docs`.

---

## 1. Ground rules (read first)

1. **The backend is frozen and verified.** 209 automated tests pin the SSE protocol,
   the plan schema, and determinism. If your code disagrees with this guide, check the
   contract files above first — then file an issue; never "fix" the backend silently.
2. **Plans are data, not code.** You render a plan document with a fixed component
   registry. Never `eval`, never inject HTML from plan strings.
3. **Full replace, no patching.** Every `ui_update` carries a complete standalone
   plan. Discard the previous plan; do not diff or merge.
4. **Everything is camelCase on the wire** except request bodies (`session_id`,
   `message`, `ui_action`, `resume` are snake_case).
5. **No auth, no persistence.** Sessions live in backend memory; a backend restart
   invalidates them (the protocol tells you, see §4).

## 2. Run the backend for development

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload     # LLM_MODE=mock by default: instant, offline
```

- Base URL: `http://127.0.0.1:8000`
- Mock mode is deterministic and returns in well under a second — build against it.
- CORS is pre-configured for `http://localhost:3000` and `http://127.0.0.1:3000`
  (Next.js dev defaults). Other origins need `ALLOWED_ORIGINS` in `backend/.env`.
  Alternatively proxy through your Next.js server routes and ignore CORS.

## 3. Endpoints

### `GET /health` → `200`

```json
{ "status": "ok", "mode": "mock" }
```

`mode` is `mock` or `real`. Use it on app boot to badge the UI.

### `POST /api/chat` → `200` (`text/event-stream`)

Request body (`application/json`):

| Field | Type | Rules |
|---|---|---|
| `session_id` | string | client-generated, **8–64 chars**, stable per conversation |
| `message` | string | ≤ 2000 chars; may be empty only when `ui_action` is present |
| `ui_action` | object \| null | `{ "type": string, "label": string, "payload": object }` |
| `resume` | boolean | default `false`; `true` = "re-attach to a session I already started" |

| Status | Meaning | Body | What the client does |
|---|---|---|---|
| 200 | turn streams as SSE | `text/event-stream` | render lifecycle (§4) |
| 404 | `resume: true` for a session the server doesn't know | `{"detail": "unknown_session"}` | drop the conversation, start fresh **without** `resume` |
| 409 | a turn is already streaming for this session | `{"detail": "turn_in_flight"}` | ignore/disable input until `turn_end`; retry if user insists |
| 422 | schema violation (id length, body empty, …) | FastAPI detail array | fix the request; it's a client bug |

Send `resume: true` when you believe the session exists but the backend may have
restarted (page reload, laptop sleep). A brand-new conversation must NOT send it.

## 4. The SSE stream — parsing and state machine

Every frame is exactly:

```
event: <type>\n
data: <one-line JSON>\n
\n
```

**Event types, in the order they can arrive:**

| # | `event:` | `data:` | Notes |
|---|---|---|---|
| 1 | `status` | `{"stage":"…"}`, `count` only on `found_n` | stages strictly in order: `intent_parsed → searching → found_n → researching → ranking → building_ui`. Clarification turns stop after `intent_parsed`. |
| 2 | `message_delta` | `{"text":"…"}` | append, in order, to the answer bubble |
| 3 | `ui_update` | the **plan document** itself (§5) | arrives once, after all deltas; full replace |
| 4 | `turn_end` | `{}` | success terminator; **unlocks input** |
| 4' | `error` | `{"message":"…","code":"structured_output"\|"internal"}` | failure terminator; **replaces** `turn_end`, nothing follows |

**Guarantees you can rely on:** statuses are gapless and ordered; ≤ 1 `ui_update` per
turn; exactly one terminal frame (`turn_end` XOR `error`); no frames after the
terminal frame.

**Client state machine:**

```
IDLE ──send──▶ STREAMING (lock previous plan, show stepper from status stages,
               append message_delta text)
STREAMING ──ui_update──▶ RENDER (replace plan region, keep input locked)
RENDER ──turn_end──▶ IDLE (unlock)
STREAMING/RENDER ──error──▶ IDLE (show error.message, unlock; keep last valid plan visible)
```

Parse robustly: accumulate the raw text and split on `\n\n`; each frame splits on the
first `\n` — `event: ` prefix on line 1, `data: ` prefix on line 2. Tolerate a final
frame without the trailing blank line (stream cut).

## 5. The UI plan document (what `ui_update` gives you)

Envelope (camelCase):

```json
{
  "planVersion": "1",
  "sessionId": "demo-12345",
  "turnId": 3,
  "root": { "type": "…", "props": { }, "actions": [ ] }
}
```

Component registry — `root.type` is exactly one of:

| Type | Props | Bounds | Allowed actions | Render as |
|---|---|---|---|---|
| `product_grid` | `title`, `productIds[]`, `ranked` | 1–6 ids | `compare`, `details`, `add_to_cart` | ranked card grid; buttons per card |
| `preference_picker` | `question`, `options[]` | 2–4 options, each has a matching `select_preference` action | `select_preference` | question + chip buttons |
| `comparison_table` | `productIds[]`, `attributes[]` | 2–3 ids | `choose` (≤1) | side-by-side table; single "Choose X" CTA |
| `product_details` | `productId`, `showQuotes` | — | none | detail card; quotes when flagged |
| `cart_view` | `items[]` (`productId`,`quantity`), `totalUsd` | — | `remove_from_cart` | cart summary + remove buttons |
| `text_block` | `body`, `heading?` | — | none | plain disclosure/notice panel |

**Action wiring — the interactive loop.** Every action has `type`, `label`,
`payload`. When the user clicks one, POST `/api/chat` with the same `session_id`,
`ui_action` set to the action object verbatim, empty `message`:

```json
{ "session_id": "demo-12345", "ui_action": { "type": "select_preference",
  "label": "Headphones", "payload": { "value": "headphones" } } }
```

Text input is the other loop: free text goes in `message`. Positional references
("compare the first two", "add that one") are resolved **server-side** against the
last rendered ranking — you never resolve them client-side.

**Prop value rules** the backend guarantees (and your renderer may assume): every
`productId` exists in the catalog; option/action counts within bounds; `choose`/`remove`
actions carry `payload.productId`.

## 6. Session lifecycle

1. Generate `session_id` when a conversation starts (8–64 chars, e.g. a uuid).
2. Keep it stable for the whole conversation; every turn repeats it.
3. On page reload / reconnect: resend history-free — send the **next user message with
   `resume: true`**. If you get `404`, the backend restarted: show a small notice
   ("session expired — starting fresh"), generate a new `session_id`, and resend
   **without** `resume`.
4. Never interleave: one in-flight turn per session (server enforces with 409).
   Disable input on send; re-enable on `turn_end`/`error`.

## 7. Contract tests you must ship

The backend ships renderable fixtures in `backend/fixtures/ui-plans/*.json` — they are
the **single source of truth** for the plan contract, and the backend already emits
plans equivalent to them:

| Fixture | Scenario |
|---|---|
| `product-grid-flights.json` | recommendation turn |
| `preference-picker-category.json` | clarify turn |
| `comparison-two.json` | "compare the first two" |
| `product-details.json` | "tell me more about this one" |
| `cart-one-item.json` | "add it to my cart" |

Your Zod schema must accept **all five fixtures** and reject: unknown component types,
foreign product ids, out-of-bounds arrays, and disallowed action types (mirror the
rules in `specs/001-backend-agent-scaffold/contracts/ui-dsl.md`). Add those five JSON
files to your test suite as render fixtures.

## 8. Backend modes and what they mean for you

- **mock** (default): deterministic, instant, no network. Answers are canned but the
  *protocol is identical* — build and test the whole UI against it. Rankings are
  byte-identical across runs; use this in CI.
- **real**: an OpenCode Zen model answers; prose varies, latency is tens of seconds —
  your steppers must tolerate long `researching` gaps. Rankings remain deterministic
  (pure scorer) even though narration varies.

## 9. Pitfalls (each of these has bitten before)

1. Don't render the plan on `message_delta` — only on `ui_update`.
2. Don't wait for `turn_end` after `error` — error is terminal.
3. Don't send `resume: true` on a brand-new session — that's a guaranteed 404.
4. Don't generate `session_id` shorter than 8 chars — 422.
5. Don't clear the transcript on `ui_update` — only the plan region is replaced; the
   answer text and history persist.
6. Don't parse `data:` lines with `JSON.parse` per line — frames are two lines +
   blank separator; split frames first.
7. `EventSource` can't POST — use `fetch` + a stream reader (or a proxy route).

## 10. Definition of done

- [ ] All five fixtures render correctly (screenshot pass) via your Zod-parsed types
- [ ] Full loop works in mock mode: grid → clarify chips → compare → details → cart
- [ ] Stepper reflects every `status` stage; input locks on send, unlocks on terminal frame
- [ ] `error` frames surface `message` + keep the last valid plan visible
- [ ] 409 handled (input disabled + retry affordance); 404 handled (fresh-session flow)
- [ ] Contract tests: five fixtures validate; known-bad plans rejected
- [ ] Works from a browser origin (CORS verified or proxied through Next routes)
- [ ] `npm run lint` / typecheck / tests green in `frontend/`
