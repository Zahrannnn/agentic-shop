"""FastAPI application factory for the agentic-shop backend (Phase 1).

``create_app`` fails fast on a misconfigured real LLM mode (research R8:
``LLM_MODE=real`` without model/key must surface at startup, not at first
request), installs the CORS allowlist from ``Settings.ALLOWED_ORIGINS``
(architecture-review fix: the Next.js frontend is a browser client, so
cross-origin requests must be answered correctly), and mounts the API
router (``/health``, ``POST /api/chat``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings, require_real_config

TAGS_METADATA = [
    {
        "name": "system",
        "description": "Liveness and configuration probes (safe to expose locally).",
    },
    {
        "name": "chat",
        "description": (
            "The conversational shopping endpoint. One POST starts one agent "
            "turn and streams it back as server-sent events. See "
            "`specs/001-backend-agent-scaffold/contracts/http-api.md` for the "
            "full contract and `FRONTEND_GUIDE.md` for a frontend-oriented guide."
        ),
    },
]

_DESCRIPTION = """Agentic shopping backend — talk to a shopping agent, get answers
plus **validated UI plan documents** your client renders (grids, comparison tables,
preference chips, cart views). No pages, no navigation.

### One endpoint, one contract

`POST /api/chat` starts **one agent turn** and streams it back as
`text/event-stream` with a fixed lifecycle:

```
status (progress stages) → message_delta (answer prose) → ui_update (full UI plan) → turn_end
```

On failure the stream ends with a single `error` frame instead of `turn_end`.

### Sessions

Identify conversations with a client-generated `session_id` (8–64 chars). Sessions
live in server memory: send `"resume": true` when re-attaching to a conversation you
already started — an unknown session answers `404 unknown_session` and you should
restart without the flag. A second message while a turn is still streaming answers
`409 turn_in_flight`.

### Modes

`LLM_MODE=mock` (default) runs the whole pipeline deterministically offline;
`LLM_MODE=real` talks to the OpenCode gateway. Mode is reported by `/health`.
"""


def create_app() -> FastAPI:
    """Build the app: fail-fast config check, CORS allowlist, API router."""
    require_real_config()
    settings = get_settings()
    application = FastAPI(
        title="agentic-shop API",
        version="1.0.0",
        summary="Conversational shopping agent with generated UI plans",
        description=_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
    )
    # Credentials stay off: the API is keyless from the browser's point of
    # view and a wildcard-with-credentials would be incoherent anyway. The
    # origin allowlist is explicit (never "*") so preflights from other
    # origins are rejected.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=False,
    )
    application.include_router(router)
    return application


app = create_app()
