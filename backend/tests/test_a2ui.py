"""D10 — A2UI v0.9 projection: goldens, round-trips, and SSE emission.

Covers (specs/003-jev-and-a2ui, PR 2):

- the five plan fixtures transpile to byte-stable golden fixtures under
  ``backend/fixtures/a2ui/`` (single source of truth, like the scorer tests);
- every plan action round-trips losslessly: after resolving ``{"path"}``
  bindings against the data model (and per-row items for grid templates), the
  A2UI event reconstructs the VERBATIM ``UIAction`` the native path sends;
- the cart amendment (D2 amendment) projects to ``deleteSurface`` + recreate;
- a mock-mode turn streams ``ui_update → a2ui_update → turn_end`` in that
  order, and the payload is a v0.9 message list for the turn's surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import collect_sse

pytestmark = pytest.mark.usefixtures("mock_settings")

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "ui-plans"
GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "a2ui"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Golden fixtures
# ---------------------------------------------------------------------------


class TestGoldens:
    @pytest.mark.parametrize("fixture", sorted(path.name for path in FIXTURES_DIR.glob("*.json")))
    def test_fixture_transpiles_to_its_golden(self, fixture: str) -> None:
        from app.a2ui import plan_to_a2ui_messages

        messages = plan_to_a2ui_messages(_load(FIXTURES_DIR / fixture))
        assert messages == _load(GOLDENS_DIR / fixture)

    def test_transpilation_is_deterministic(self) -> None:
        from app.a2ui import plan_to_a2ui_messages

        plan = _load(FIXTURES_DIR / "product-grid-flights.json")
        assert plan_to_a2ui_messages(plan) == plan_to_a2ui_messages(plan)

    def test_every_message_pins_the_wire_version(self) -> None:
        from app.a2ui import A2UI_VERSION, plan_to_a2ui_messages

        for name in sorted(path.name for path in FIXTURES_DIR.glob("*.json")):
            for message in plan_to_a2ui_messages(_load(FIXTURES_DIR / name)):
                assert message["version"] == A2UI_VERSION

    def test_cart_amendment_deletes_the_amended_surface(self) -> None:
        from app.a2ui import plan_to_a2ui_messages

        plan = _load(FIXTURES_DIR / "cart-one-item.json")
        plan["amendsTurnId"] = 1
        plan["turnId"] = 3
        messages = plan_to_a2ui_messages(plan)
        assert messages[0] == {
            "version": "v0.9",
            "deleteSurface": {"surfaceId": "spec-fixture-1"},
        }
        assert messages[1]["createSurface"]["surfaceId"] == "spec-fixture-3"


# ---------------------------------------------------------------------------
# Lossless action round-trip
# ---------------------------------------------------------------------------


def _messages_parts(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    components: list[dict[str, Any]] = []
    data: dict[str, Any] = {}
    for message in messages:
        if "updateComponents" in message:
            components = message["updateComponents"]["components"]
        if "updateDataModel" in message:
            data = message["updateDataModel"]["value"]
    return components, data


def _resolve(value: Any, data: dict[str, Any], item: dict[str, Any] | None) -> Any:
    """Resolve a Dynamic* binding: literal, absolute ``{"path": "/..."}``
    against the data model, or relative ``{"path"}`` in a template item scope."""
    if not (isinstance(value, dict) and set(value) == {"path"}):
        return value
    pointer = value["path"]
    scope: Any = data if pointer.startswith("/") else (item or {})
    if pointer.startswith("/"):
        pointer = pointer[1:]
        if not pointer:
            return scope
    node: Any = scope
    for part in pointer.split("/"):
        node = node[part]
    return node


class TestActionRoundTrip:
    def _reconstructed_actions(self, fixture: str) -> list[dict[str, Any]]:
        """Every (action, row-item) pair reconstructed as a native UIAction."""
        from app.a2ui import plan_to_a2ui_messages

        components, data = _messages_parts(plan_to_a2ui_messages(_load(FIXTURES_DIR / fixture)))
        template = next(
            (
                component["children"]
                for component in components
                if component.get("component") == "List"
                and isinstance(component.get("children"), dict)
            ),
            None,
        )
        row_items: list[dict[str, Any]] = (
            _resolve({"path": template["path"]}, data, None) if template else []
        )

        reconstructed: list[dict[str, Any]] = []
        for component in components:
            event = (component.get("action") or {}).get("event")
            if event is None:
                continue
            contexts: list[dict[str, Any]] = [event["context"]]
            # Per-row buttons resolve once per data item (grid card stamping).
            if (
                any(
                    isinstance(value, dict) and str(value.get("path", "")) == "id"
                    for value in event["context"].values()
                )
                and row_items
            ):
                contexts = [
                    {key: _resolve(value, data, item) for key, value in event["context"].items()}
                    for item in row_items
                ]
            for context in contexts:
                payload = {key: value for key, value in context.items() if key != "label"}
                reconstructed.append(
                    {"type": event["name"], "label": context["label"], "payload": payload}
                )
        return reconstructed

    def _expected_actions(self, fixture: str) -> list[dict[str, Any]]:
        """The native set: verbatim actions, per-card ones stamped per product
        (mirroring ``withProduct`` — compare stays grid-level)."""
        plan = _load(FIXTURES_DIR / fixture)
        actions = plan["root"]["actions"]
        products = plan["root"]["props"].get("products") or []
        expected: list[dict[str, Any]] = []
        for action in actions:
            if action["type"] in {"details", "add_to_cart"} and products:
                for product in products:
                    expected.append(
                        {
                            "type": action["type"],
                            "label": action["label"],
                            "payload": {**action["payload"], "productId": product["id"]},
                        }
                    )
            else:
                expected.append(
                    {
                        "type": action["type"],
                        "label": action["label"],
                        "payload": dict(action["payload"]),
                    }
                )
        return expected

    @pytest.mark.parametrize("fixture", sorted(path.name for path in FIXTURES_DIR.glob("*.json")))
    def test_every_action_round_trips_verbatim(self, fixture: str) -> None:
        reconstructed = sorted(
            map(
                json.dumps,
                self._reconstructed_actions(fixture),
            )
        )
        expected = sorted(map(json.dumps, self._expected_actions(fixture)))
        assert reconstructed == expected


# ---------------------------------------------------------------------------
# SSE emission
# ---------------------------------------------------------------------------


class TestSseEmission:
    async def test_order_is_ui_update_then_a2ui_then_turn_end(self, client) -> None:
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "a2ui-order-check-1",
                "message": "Best headphones for long flights under $200",
            },
        ) as response:
            events = await collect_sse(response)

        names = [name for name, _ in events]
        assert names.index("ui_update") < names.index("a2ui_update") < names.index("turn_end")
        plan = dict(events[names.index("ui_update")][1])
        messages = events[names.index("a2ui_update")][1]["messages"]
        assert isinstance(messages, list) and messages
        assert messages[0]["createSurface"]["surfaceId"] == (
            f"{plan['sessionId']}-{plan['turnId']}"
        )

    async def test_clarify_ask_turn_also_projects(self, client) -> None:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"session_id": "a2ui-clarify-check", "message": "I want something nice"},
        ) as response:
            events = await collect_sse(response)

        names = [name for name, _ in events]
        assert "ui_update" in names and "a2ui_update" in names
        assert names[-1] == "turn_end"
        messages = events[names.index("a2ui_update")][1]["messages"]
        components = next(
            m["updateComponents"]["components"] for m in messages if "updateComponents" in m
        )
        assert any(c["id"] == "picker-question" for c in components)

    async def test_projection_failure_never_fails_a_turn(self, client, monkeypatch) -> None:
        """D10: the frozen ui_update path is the truth — a broken projection
        skips its own frame and the turn still completes normally."""

        def exploding(plan):  # noqa: ANN001
            raise RuntimeError("projection exploded")

        monkeypatch.setattr("app.graph.nodes.plan_to_a2ui_messages", exploding)
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "a2ui-explode-check",
                "message": "Best headphones for long flights under $200",
            },
        ) as response:
            events = await collect_sse(response)

        names = [name for name, _ in events]
        assert "ui_update" in names
        assert "a2ui_update" not in names
        assert names[-1] == "turn_end"
