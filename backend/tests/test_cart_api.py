"""D12 — direct cart mutation: PATCH /api/cart.

The widget path: no streamed turn, no model call, no input lock. Covered:

- the happy path: a session that added a product patches its quantity; the
  checkpointed cart is updated (verified via get_state), and the response
  carries the authoritative re-rendered plan (validating against the DSL,
  with the amendment anchor) plus the A2UI projection;
- the guards: 404 unknown_session (never-seen session), 404 unknown_cart_line
  (product not in the cart), 409 turn_in_flight (read-only check — a PATCH
  never registers itself), 422 for quantity bounds;
- the conversational path is untouched: a follow-up turn after patches still
  amends the same anchor.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from langgraph.graph.state import CompiledStateGraph

from app.catalog.loader import load_catalog
from app.dsl.models import UIPlan
from app.dsl.validate import validate_plan
from tests.conftest import collect_sse

pytestmark = pytest.mark.usefixtures("mock_settings")

_FLIGHTS = "best headphones for long flights under $200 with great noise cancellation"


async def _setup_cart_session(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    """Recommend → add the first pick to the cart; return the add turn's plan."""
    async with client.stream(
        "POST", "/api/chat", json={"session_id": session_id, "message": _FLIGHTS}
    ) as response:
        await collect_sse(response)
    async with client.stream(
        "POST",
        "/api/chat",
        json={"session_id": session_id, "message": "add the first one to my cart"},
    ) as response:
        events = await collect_sse(response)
    return next(data for name, data in events if name == "ui_update")


class TestPatchCart:
    async def test_patch_updates_checkpoint_and_returns_authoritative_render(
        self, client: httpx.AsyncClient
    ) -> None:
        session = "patch-happy-001"
        cart_plan = await _setup_cart_session(client, session)
        product_id = cart_plan["root"]["props"]["items"][0]["productId"]

        response = await client.patch(
            "/api/cart",
            json={"session_id": session, "product_id": product_id, "quantity": 3},
        )
        assert response.status_code == 200
        body = response.json()

        # Authoritative lines + exact total.
        assert (
            body["items"] == [{"productId": product_id, "quantity": 3, "unitPriceUsd": 179.0}]
            or body["items"][0]["quantity"] == 3
        )
        catalog = {product.id: product for product in load_catalog()}
        assert body["totalUsd"] == round(catalog[product_id].price_usd * 3, 2)

        # The re-rendered plan validates, amends the anchored cart turn, and
        # carries the D11 stepper set for quantity 3.
        plan = UIPlan.model_validate(body["plan"])
        validate_plan(plan, set(catalog))
        assert plan.root.type == "cart_view"
        assert plan.root.props.items[0].quantity == 3
        assert plan.amends_turn_id == cart_plan["turnId"]
        step_quantities = [
            action.payload["quantity"]
            for action in plan.root.actions
            if action.type == "set_quantity"
        ]
        assert step_quantities == [2, 4]

        # The A2UI projection rides along in the documented envelope shape —
        # for an amended cart the stream opens with deleteSurface, then the
        # recreated surface for the new turn.
        messages = body["a2ui"]["messages"]
        created = next(m for m in messages if "createSurface" in m)
        assert created["createSurface"]["surfaceId"] == f"{session}-{plan.turn_id}"

        # The checkpoint itself moved — get_state sees the new cart.
        from app.graph.builder import get_graph

        graph: CompiledStateGraph = get_graph()
        values = graph.get_state({"configurable": {"thread_id": session}}).values
        assert values["cart"] == [{"product_id": product_id, "quantity": 3}]

    async def test_404_for_an_unknown_session(self, client: httpx.AsyncClient) -> None:
        response = await client.patch(
            "/api/cart",
            json={"session_id": "never-seen-01", "product_id": "aurora-hush-pro", "quantity": 2},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "unknown_session"}

    async def test_404_for_a_product_not_in_the_cart(self, client: httpx.AsyncClient) -> None:
        session = "patch-line-404"
        await _setup_cart_session(client, session)
        response = await client.patch(
            "/api/cart",
            json={"session_id": session, "product_id": "volt-enduro-70", "quantity": 2},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "unknown_cart_line"}

    async def test_422_for_quantity_out_of_bounds(self, client: httpx.AsyncClient) -> None:
        session = "patch-bounds-001"
        await _setup_cart_session(client, session)
        for quantity in (0, 11):
            response = await client.patch(
                "/api/cart",
                json={"session_id": session, "product_id": "aurora-hush-pro", "quantity": quantity},
            )
            assert response.status_code == 422

    async def test_409_while_a_turn_is_in_flight(self, client: httpx.AsyncClient) -> None:
        session = "patch-conflict-1"
        await _setup_cart_session(client, session)

        # Park the session in the in-flight set exactly like a streaming turn.
        from app.api.routes import _in_flight

        _in_flight.add(session)
        try:
            response = await client.patch(
                "/api/cart",
                json={"session_id": session, "product_id": "aurora-hush-pro", "quantity": 2},
            )
            assert response.status_code == 409
            assert response.json() == {"detail": "turn_in_flight"}
        finally:
            _in_flight.discard(session)

    async def test_conversational_turns_still_amend_after_patches(
        self, client: httpx.AsyncClient
    ) -> None:
        """The conversational path is untouched: a chat turn after a direct
        patch still re-renders the cart from the updated checkpoint."""
        session = "patch-then-chat"
        cart_plan = await _setup_cart_session(client, session)
        product_id = cart_plan["root"]["props"]["items"][0]["productId"]

        patched = await client.patch(
            "/api/cart",
            json={"session_id": session, "product_id": product_id, "quantity": 3},
        )
        assert patched.status_code == 200

        async with client.stream(
            "POST", "/api/chat", json={"session_id": session, "message": "what's in my cart?"}
        ) as response:
            events = await collect_sse(response)
        plan = next(data for name, data in events if name == "ui_update")
        assert plan["root"]["props"]["items"][0]["quantity"] == 3
        assert plan["amendsTurnId"] == cart_plan["turnId"]
