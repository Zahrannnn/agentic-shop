"""HTTP routes: ``GET /health``, ``GET /api/catalog``, and SSE chat (D7).

The chat endpoint drives the compiled graph with ``astream(...,
stream_mode="custom")`` and translates the nodes' ``(kind, data)`` payloads
1:1 into ``event: <type>\\ndata: <json>\\n\\n`` frames (research R2/R3) —
no SSE library, the event vocabulary is tiny.

Frame order per turn is the contract's fixed order; ``turn_end`` closes every
successful turn. Exactly one terminal frame is ever sent: an in-stream
``StructuredOutputError`` or a node-emitted ``error`` payload replaces
``turn_end`` and nothing follows it.

Concurrency (FR-016): at most one turn may be in flight per ``session_id``;
a second concurrent POST for the same session is rejected with **409**
before the stream starts (``{"detail": "turn_in_flight"}``); other sessions
are unaffected. The in-flight registration happens in the endpoint body, the
generator's ``finally`` releases it.

Sessions (``resume`` flag, architecture-review fix): :data:`_live_sessions`
records every session that started a turn in THIS process. A request with
``resume=true`` for a session outside that set is rejected with **404**
(``{"detail": "unknown_session"}``) BEFORE the busy guard — sessions are
in-memory, so after a restart the client's reattach attempt 404s and it MUST
start a fresh session (retry without ``resume``). ``resume=false`` always
proceeds and registers the session; entries are never removed (a restart
wipes the process set — exactly the contract's restart story).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    CatalogProductOut,
    CatalogResponse,
    ChatRequest,
    ErrorEvent,
    MessageDeltaEvent,
    ProtocolEvent,
    SSEEvent,
    StatusEvent,
    TurnEndEvent,
    UIUpdateEvent,
)
from app.config import get_settings
from app.graph.builder import get_graph
from app.graph.nodes import get_catalog
from app.llm.client import StructuredOutputError

router = APIRouter()

#: Sessions with a turn currently streaming (FR-016). Mutated only under
#: :data:`_in_flight_lock`; registered in the endpoint, released in the
#: stream generator's ``finally``.
_in_flight: set[str] = set()
_in_flight_lock = asyncio.Lock()

#: Sessions this process has seen start a turn (``resume`` support). Mutated
#: only under :data:`_in_flight_lock`; never emptied except by a process
#: restart — which is exactly the semantics the 404 contract describes.
_live_sessions: set[str] = set()
_live_sessions_lock = _in_flight_lock  # same critical section guards both sets

_STRUCTURED_OUTPUT_ERROR_MESSAGE = "The model returned an invalid response twice. Please try again."
_INTERNAL_ERROR_MESSAGE = "Something went wrong on our side. Please try again."


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    tags=["system"],
    summary="Liveness probe plus the effective LLM mode",
    description=(
        'Returns `{"status": "ok"}` and the effective mode: `mock` (deterministic, '
        "keyless, offline) or `real` (OpenCode gateway). Never echoes secrets."
    ),
    responses={
        200: {
            "description": "Service is up.",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "mode": "mock"},
                    "examples": {
                        "mock": {
                            "summary": "Mock mode (default)",
                            "value": {"status": "ok", "mode": "mock"},
                        },
                        "real": {
                            "summary": "Real gateway model configured",
                            "value": {"status": "ok", "mode": "real"},
                        },
                    },
                }
            },
        }
    },
)
async def health() -> dict[str, str]:
    """Liveness plus the effective LLM mode; never echoes secrets."""
    return {"status": "ok", "mode": "mock" if get_settings().is_mock else "real"}


# ---------------------------------------------------------------------------
# Catalog (read-only)
# ---------------------------------------------------------------------------


@router.get(
    "/api/catalog",
    tags=["catalog"],
    summary="The full curated product catalog, cheapest first",
    description=(
        "Returns every validated catalog product as a JSON dump: `count` plus a "
        "`products` array sorted by `priceUsd` ascending (id ascending on ties, "
        "so the order is deterministic).\n\n"
        "Keys are camelCase to match the UI-plan DSL. Review **quotes are "
        "deliberately excluded** — this endpoint is for browsing and rendering; "
        "quote text only ever flows through the chat pipeline (`get_product_reviews`)."
    ),
    responses={
        200: {
            "description": "The current catalog snapshot (static per process).",
            "content": {
                "application/json": {
                    "example": {
                        "count": 2,
                        "products": [
                            {
                                "id": "pockettone-basis-29",
                                "name": "Pockettone Basis 29",
                                "brand": "Pockettone",
                                "category": "earbuds",
                                "priceUsd": 29.0,
                                "batteryHours": 6.0,
                                "weightG": 4.2,
                                "ancType": "none",
                                "reviewScores": {
                                    "comfort": 3.9,
                                    "anc": 1.8,
                                    "sound": 3.2,
                                    "battery": 3.5,
                                    "value": 4.3,
                                },
                                "multipoint": False,
                                "folding": False,
                                "codecs": ["sbc", "aac"],
                            }
                        ],
                    }
                }
            },
        }
    },
)
async def catalog() -> CatalogResponse:
    """Dump the validated catalog, price-ascending (id breaks ties)."""
    products = sorted(get_catalog(), key=lambda product: (product.price_usd, product.id))
    return CatalogResponse(
        count=len(products),
        products=[
            CatalogProductOut.model_validate(product, from_attributes=True) for product in products
        ],
    )


# ---------------------------------------------------------------------------
# Chat (SSE)
# ---------------------------------------------------------------------------


def _payload_to_event(kind: str, data: Any) -> ProtocolEvent | None:
    """Translate a node's custom stream payload into its protocol event model."""
    if kind == "status":
        return StatusEvent(stage=data["stage"], count=data.get("count"))
    if kind == "message_delta":
        return MessageDeltaEvent(text=data["text"])
    if kind == "ui_update":
        return UIUpdateEvent(plan=data)
    if kind == "error":
        return ErrorEvent(
            message=str(data.get("message", _INTERNAL_ERROR_MESSAGE)),
            code=data.get("code", "internal"),
        )
    return None


def _payload_to_frame(kind: str, data: Any) -> str | None:
    """Render one node payload as a wire frame (or ``None`` for unknown kinds).

    ``ui_update`` is special-cased: contracts/http-api.md and ui-dsl.md require
    the ``data:`` payload to BE the plan envelope itself, so it is serialized
    directly instead of wrapped in :class:`UIUpdateEvent`'s ``plan`` key.
    """
    if kind == "ui_update":
        return SSEEvent(event="ui_update", data=json.dumps(data, separators=(",", ":"))).frame()
    event = _payload_to_event(kind, data)
    return None if event is None else event.to_frame().frame()


async def sse_generator(
    graph_input: dict[str, Any],
    config: dict[str, Any],
    session_id: str,
) -> AsyncIterator[str]:
    """Stream one turn as D7 SSE frames, then release the session slot.

    Terminal-frame invariant: exactly one of ``turn_end`` / ``error`` ends the
    stream. A node-emitted ``error`` payload or a raised
    :class:`StructuredOutputError` suppresses ``turn_end``.
    """
    errored = False
    # D7 contract order: statuses -> message_delta -> ui_update -> turn_end.
    # Nodes stream the plan before the narration (D6 runs ui_plan before
    # respond), so the ui_update frame is deferred to preserve the wire order
    # without buffering the prose. A failed turn drops the deferred plan: the
    # error frame is the sole terminal output.
    deferred_ui_frame: str | None = None
    try:
        try:
            async for payload in get_graph().astream(
                graph_input, config=config, stream_mode="custom"
            ):
                if not (isinstance(payload, tuple) and len(payload) == 2):
                    continue
                kind, data = payload
                if kind == "error":
                    errored = True
                frame = _payload_to_frame(kind, data)
                if frame is None:
                    continue
                if kind == "ui_update":
                    deferred_ui_frame = frame
                    continue
                yield frame
        except StructuredOutputError:
            errored = True
            yield (
                ErrorEvent(message=_STRUCTURED_OUTPUT_ERROR_MESSAGE, code="structured_output")
                .to_frame()
                .frame()
            )
        except Exception:
            errored = True
            yield ErrorEvent(message=_INTERNAL_ERROR_MESSAGE, code="internal").to_frame().frame()
        if not errored:
            if deferred_ui_frame is not None:
                yield deferred_ui_frame
            yield TurnEndEvent().to_frame().frame()
    finally:
        _in_flight.discard(session_id)


_SSE_SUCCESS_EXAMPLE = (
    'event: status\ndata: {"stage":"intent_parsed"}\n\n'
    'event: status\ndata: {"stage":"searching"}\n\n'
    'event: status\ndata: {"stage":"found_n","count":14}\n\n'
    'event: status\ndata: {"stage":"researching"}\n\n'
    'event: status\ndata: {"stage":"ranking"}\n\n'
    'event: status\ndata: {"stage":"building_ui"}\n\n'
    'event: message_delta\ndata: {"text":"Based on your priorities, here are my top picks."}\n\n'
    'event: message_delta\ndata: {"text":"Aurora Hush Pro ($179): adaptive ANC rated 4.9/5..."}\n\n'
    'event: ui_update\ndata: {"planVersion":"1","sessionId":"demo-12345","turnId":1,'
    '"root":{"type":"product_grid","props":{"title":"Best matches for your needs",'
    '"productIds":["aurora-hush-pro","cloudline-air","maple-ridge-comfort-150"],'
    '"ranked":true},"actions":[{"type":"compare","label":"Compare","payload":{}}]}}\n\n'
    "event: turn_end\ndata: {}\n\n"
)


@router.post(
    "/api/chat",
    tags=["chat"],
    summary="Start one streamed agent turn (SSE)",
    description=(
        "Accepts one natural-language message (or a `ui_action` from a rendered plan) "
        "and streams the agent's turn back as `text/event-stream`.\n\n"
        "**Frame order (fixed):** zero or more `status` (stages in order "
        "`intent_parsed → searching → found_n → researching → ranking → building_ui`), "
        "then `message_delta` prose increments, then at most one `ui_update` carrying "
        "a **full UI plan** (full replace — never a delta), then exactly one terminal "
        "frame: `turn_end` on success, `error` on failure (nothing follows it).\n\n"
        "**Sessions:** `session_id` scopes the conversation; state lives in server "
        "memory. Send `resume: true` when re-attaching to a conversation this server "
        "may not know (e.g. after a restart) — an unknown session answers **404** and "
        "the client should restart without the flag.\n\n"
        "**Plan documents:** `ui_update` data is the plan envelope itself. The "
        "component registry, prop bounds, and allowed actions are specified in "
        "`specs/001-backend-agent-scaffold/contracts/ui-dsl.md`, with renderable "
        "examples in `backend/fixtures/ui-plans/*.json`."
    ),
    responses={
        200: {
            "description": (
                "One agent turn as `text/event-stream`. Frames are "
                "`event: <type>\\ndata: <json>\\n\\n`; exactly one of `turn_end` / "
                "`error` terminates the stream."
            ),
            "content": {
                "text/event-stream": {
                    "example": _SSE_SUCCESS_EXAMPLE,
                }
            },
        },
        404: {
            "description": (
                "`resume: true` was sent for a session this server process does not "
                "know (never seen, or restarted since). Restart the conversation "
                "without the `resume` flag."
            ),
            "content": {"application/json": {"example": {"detail": "unknown_session"}}},
        },
        409: {
            "description": (
                "A turn is already streaming for this `session_id`; other sessions "
                "are unaffected. Wait for `turn_end`, then retry."
            ),
            "content": {"application/json": {"example": {"detail": "turn_in_flight"}}},
        },
        422: {
            "description": (
                "Request body violates the schema (session_id length, message length, "
                "or a body with neither a message nor a ui_action)."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "session_id"],
                                "msg": "String should have at least 8 characters",
                                "type": "string_too_short",
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def chat(request: ChatRequest) -> StreamingResponse:
    """Start one streamed turn for ``session_id``.

    Guard order under one lock (architecture-review fix): ``resume=true``
    for a session this process never registered -> **404 unknown_session**
    first; then the FR-016 busy guard -> **409 turn_in_flight**; otherwise
    the turn starts and the session is registered as live.
    """
    session_id = request.session_id
    async with _live_sessions_lock:
        if request.resume and session_id not in _live_sessions:
            raise HTTPException(status_code=404, detail="unknown_session")
        if session_id in _in_flight:
            raise HTTPException(status_code=409, detail="turn_in_flight")
        _in_flight.add(session_id)
        _live_sessions.add(session_id)
    graph_input = {
        "pending_user_text": request.message,
        "pending_ui_action": request.ui_action.model_dump() if request.ui_action else None,
        "session_id": session_id,
    }
    config = {"configurable": {"thread_id": session_id}}
    return StreamingResponse(
        sse_generator(graph_input, config, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
