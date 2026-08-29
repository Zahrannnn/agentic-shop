"""HTTP API protocol models: chat request body and SSE event frames.

Wire contract: ``specs/001-backend-agent-scaffold/contracts/http-api.md``
(DECISIONS.md D7). This module is the single source of truth for:

* :class:`ChatRequest` — the ``POST /api/chat`` JSON body (snake_case keys,
  exactly as the contract specifies; no aliasing here).
* Server->client event payload models, each with a :meth:`to_frame` helper
  that serializes to compact single-line JSON wrapped in an :class:`SSEEvent`.
* :class:`SSEEvent` — one pre-serialized SSE frame and the only framing
  helper the routes should use.

Event payloads dump with ``by_alias=True`` so any wire-level camelCase only
needs an ``alias=`` on the field; today every payload field is a single
lowercase word (``stage``, ``count``, ``text``, ``plan``, ``message``,
``code``) and the ``found_n`` stage name is the exact contract string.
"""

import json
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

__all__ = [
    "STAGE_ORDER",
    "ChatRequest",
    "ErrorEvent",
    "MessageDeltaEvent",
    "ProtocolEvent",
    "SSEEvent",
    "Stage",
    "StatusEvent",
    "TurnEndEvent",
    "UIActionIn",
    "UIUpdateEvent",
]

Stage = Literal[
    "intent_parsed",
    "searching",
    "found_n",
    "researching",
    "ranking",
    "building_ui",
]
"""Stage values of ``status`` events, in the contract's exact spelling."""

STAGE_ORDER: tuple[Stage, ...] = (
    "intent_parsed",
    "searching",
    "found_n",
    "researching",
    "ranking",
    "building_ui",
)
"""Fixed stage order for order checks (``intent_parsed → … → building_ui``)."""


class UIActionIn(BaseModel):
    """A rendered plan action echoed back by the client (data-model.md ``UIAction``)."""

    type: str
    label: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Body of ``POST /api/chat`` (contracts/http-api.md).

    Keys stay snake_case per the contract. A valid turn needs at least one
    of ``message`` (non-empty after whitespace-stripping) or ``ui_action``.

    ``resume`` is additive and backward-compatible (architecture-review fix):
    it lets a client distinguish "reattach to a session I already started"
    from "start a new one". ``resume=true`` on a session this backend process
    has never seen is rejected with ``404 unknown_session`` BEFORE any turn
    starts (contracts/http-api.md: after a backend restart the client
    receives 404 and MUST start a new session, i.e. retry without the flag);
    ``resume=false`` always proceeds and registers the session.
    """

    session_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=8, max_length=64),
    ]
    message: Annotated[str, StringConstraints(max_length=2000)] = ""
    ui_action: UIActionIn | None = None
    resume: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "First message of a new session",
                    "value": {
                        "session_id": "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
                        "message": (
                            "Help me find the best headphones for long flights "
                            "under $200. Noise cancellation and comfort matter most."
                        ),
                    },
                },
                {
                    "summary": "Re-attach to an existing session after a reload",
                    "value": {
                        "session_id": "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
                        "message": "compare the first two",
                        "resume": True,
                    },
                },
                {
                    "summary": "UI action tapped on a rendered plan (no text)",
                    "value": {
                        "session_id": "b1e0c8de-2f6a-4c6f-9a4d-2f1e0b9c8d77",
                        "ui_action": {
                            "type": "add_to_cart",
                            "label": "Add to cart",
                            "payload": {"productId": "aurora-hush-pro"},
                        },
                    },
                },
            ]
        }
    )

    @model_validator(mode="after")
    def _require_message_or_ui_action(self) -> Self:
        """Reject turns carrying neither a message nor a UI action."""
        if not (self.message.strip() or self.ui_action is not None):
            raise ValueError("either a non-empty 'message' or a 'ui_action' is required")
        return self


class SSEEvent(BaseModel):
    """A single serialized SSE frame: ``event: <type>`` + ``data: <json>``."""

    event: str
    data: str

    def frame(self) -> str:
        """Render the wire frame; the only framing helper routes should use."""
        return f"event: {self.event}\ndata: {self.data}\n\n"

    def __str__(self) -> str:
        return self.frame()


class _ProtocolEvent(BaseModel):
    """Base for server->client SSE payloads (data-model.md, protocol entities)."""

    event_name: ClassVar[str]

    def to_frame(self) -> SSEEvent:
        """Serialize to an :class:`SSEEvent` carrying compact single-line JSON."""
        payload = json.dumps(
            self.model_dump(mode="json", by_alias=True, exclude_none=True),
            separators=(",", ":"),
        )
        return SSEEvent(event=self.event_name, data=payload)


class StatusEvent(_ProtocolEvent):
    """``status`` — progress stage; only ``found_n`` carries ``count``."""

    event_name: ClassVar[str] = "status"

    stage: Stage
    count: int | None = None


class MessageDeltaEvent(_ProtocolEvent):
    """``message_delta`` — prose increments of the answer."""

    event_name: ClassVar[str] = "message_delta"

    text: str


class UIUpdateEvent(_ProtocolEvent):
    """``ui_update`` — the validated UI-plan DSL document, full replace (D2).

    ``plan`` is a passthrough dict: it is validated against the DSL
    (``app/dsl``) by the graph before being wrapped here, never re-shaped.
    """

    event_name: ClassVar[str] = "ui_update"

    plan: dict[str, Any]


class TurnEndEvent(_ProtocolEvent):
    """``turn_end`` — empty payload; unlocks the client."""

    event_name: ClassVar[str] = "turn_end"


class ErrorEvent(_ProtocolEvent):
    """``error`` — terminal frame; replaces ``turn_end``, nothing follows it."""

    event_name: ClassVar[str] = "error"

    message: str
    code: Literal["structured_output", "busy", "unknown_session", "internal"] = "internal"


ProtocolEvent = StatusEvent | MessageDeltaEvent | UIUpdateEvent | TurnEndEvent | ErrorEvent
"""Union of every server->client event payload model, for route type hints."""
