# Contract: HTTP API + SSE Protocol

**Feature**: `001-backend-agent-scaffold` | **Date**: 2026-08-29

This is the backend's only external interface in Phase 1. It implements
DECISIONS.md D7 verbatim. The future Next.js frontend consumes exactly this
contract; command-line tools are first-class clients for testing.

## Conventions

- Base URL: `http://127.0.0.1:8000` (local dev default; port is not part of
  the contract).
- All bodies are JSON (`application/json`); the chat response is
  `text/event-stream`.
- Errors that prevent streaming use standard HTTP status codes with a JSON
  body `{"detail": string}`; errors mid-stream use the `error` SSE event.

## Endpoints

### `GET /health`

- **200** → `{"status": "ok", "mode": "mock" | "real"}` — liveness plus the
  effective LLM mode (never echoes secrets).

### `POST /api/chat`

Request body (`ChatRequest`):

```json
{
  "session_id": "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
  "message": "Help me find the best headphones for long flights under $200.",
  "ui_action": null,
  "resume": false
}
```

| Field | Type | Rules |
|---|---|---|
| `session_id` | string | client-generated, 8–64 chars; scopes the conversation |
| `message` | string | 1–2000 chars; omit/empty only when `ui_action` present |
| `ui_action` | object \| null | `{type, label, payload}` echoed from a rendered plan component |
| `resume` | boolean | default `false`. Set `true` when the client believes the session already exists (e.g. restoring a conversation after a page reload); the server answers `404` if it does not know the session |

Responses:

- **200** — SSE stream (below).
- **404 Not Found** — `resume: true` for a session the server does not know
  (process restarted or never seen). Body: `{"detail": "unknown_session"}`.
  The client MUST restart the conversation without `resume`. Requests with
  `resume: false` (the default) always proceed and register the session.
- **409 Conflict** — a turn is already in flight for this `session_id`
  (FR-016). Body: `{"detail": "turn_in_flight"}`. Other sessions unaffected.
  Takes precedence *after* the 404 check (an unknown-and-busy session answers
  404 when `resume: true`, 409 otherwise).
- **422 Unprocessable Entity** — schema-violating request body (FastAPI
  validation).

## Cross-origin (browser clients)

The API sends permissive-enough CORS headers for browser frontends: allowed
origins are configured server-side via `ALLOWED_ORIGINS` (comma-separated;
defaults cover the Next.js dev server on `localhost:3000` / `127.0.0.1:3000`),
with methods `GET, POST, OPTIONS` and headers `Content-Type, Authorization`,
credentials disabled. Alternatively a client may proxy all calls through its
own server routes and ignore CORS entirely.

## SSE stream (success)

Content type `text/event-stream`; each frame is `event: <type>\n` +
`data: <single-line JSON>\n\n`. Frame order per turn is fixed:

```
event: status        data: {"stage":"intent_parsed"}
event: status        data: {"stage":"searching"}
event: status        data: {"stage":"found_n","count":14}
event: status        data: {"stage":"researching"}
event: status        data: {"stage":"ranking"}
event: status        data: {"stage":"building_ui"}
event: message_delta data: {"text":"Based on "}
event: message_delta data: {"text":"your priorities, "}
...
event: ui_update     data: {<full UI plan — see contracts/ui-dsl.md>}
event: turn_end      data: {}
```

Stage values and order: `intent_parsed → searching → found_n → researching →
ranking → building_ui`. `found_n` carries `count`.

Clarification turn (ask path) — no downstream stages run, the plan is the
preference picker, turn still ends normally:

```
event: status        data: {"stage":"intent_parsed"}
event: message_delta data: {"text":"Which category are you shopping for?"}
event: ui_update     data: {<preference_picker plan>}
event: turn_end      data: {}
```

## SSE stream (failure)

Exactly one terminal frame replaces `turn_end`; no frames follow it:

```
event: error         data: {"message":"The model returned an invalid
                              response twice. Please try again.","code":"structured_output"}
```

Error codes: `structured_output` (D8 wrapper exhausted its retry),
`busy` (mirrors 409 if raced), `unknown_session`, `internal` (unexpected;
message is safe for display, never raw model output or stack traces).

## Client obligations (frontend contract, D7)

- First `status` of a new turn → lock the previous plan region and show a
  progress stepper.
- `ui_update` → render the full plan, replacing the previous one (D2).
- `turn_end` → unlock; `error` → show message, unlock.

## Multi-turn semantics

- Same `session_id` resumes checkpointed state (LangGraph `thread_id`).
- `ui_action` present → the action is resolved against the session's last
  plan/ranking (positional references like "the first two" come in as `message`
  text and are resolved in-graph from session state).
- Sessions are in-memory: after a backend restart the client receives
  `404 unknown_session` and MUST start a new session.
