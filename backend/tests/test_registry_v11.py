"""D11 interactive-registry behavior: refine loop, steppers, priorities ask.

Graph-level tests over the SSE stream (mock mode, deterministic):

- the priorities ask (D4 amendment): a known category with NO stated
  priorities asks the multi_picker exactly once; answering it re-ranks;
  conversations with stated priorities skip it; a follow-up turn never
  triggers it;
- the refinement loop: a ``refine`` chip re-runs the pipeline in ONE turn —
  the fresh grid echoes the applied state, carries a Clear chip, orders by
  the chosen sort, and never makes an intent model call;
- cart steppers: the cart plan ships only in-bounds steps, a ``set_quantity``
  action updates the line and amends the anchored cart turn in place.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.catalog.loader import load_catalog
from tests.conftest import collect_sse

pytestmark = pytest.mark.usefixtures("mock_settings")

_FLIGHTS_NO_PRIORITY = "Best headphones for long flights under $200"
_FLIGHTS_WITH_PRIORITY = "Best headphones for long flights under $200 with great noise cancellation"


async def _turn(
    client, session_id: str, payload: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    async with client.stream(
        "POST", "/api/chat", json={"session_id": session_id, **payload}
    ) as response:
        return await collect_sse(response)


def _plan_of(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    return next(data for name, data in events if name == "ui_update")


class TestPrioritiesAsk:
    async def test_asks_once_then_reranks_on_the_answer(self, client) -> None:
        session = "v11-priorities-01"
        events1 = await _turn(client, session, {"message": _FLIGHTS_NO_PRIORITY})
        plan1 = _plan_of(events1)
        assert plan1["root"]["type"] == "multi_picker"
        assert plan1["root"]["props"]["maxSelect"] == 2
        actions1 = plan1["root"]["actions"]
        assert [action["type"] for action in actions1] == ["select_preferences"]
        assert actions1[0]["payload"] == {"values": []}  # the unstamped template
        assert events1[-1][0] == "turn_end"

        # The answer: the client stamps the checked option names.
        events2 = await _turn(
            client,
            session,
            {
                "ui_action": {
                    "type": "select_preferences",
                    "label": "Show my picks",
                    "payload": {"values": ["Noise cancellation", "Comfort"]},
                }
            },
        )
        plan2 = _plan_of(events2)
        assert plan2["root"]["type"] == "product_grid"
        assert events2[-1][0] == "turn_end"

        # Never twice: the next free-text turn proceeds without asking.
        events3 = await _turn(client, session, {"message": "and something cheaper"})
        plan3 = _plan_of(events3)
        assert plan3["root"]["type"] == "product_grid"

    async def test_skipped_when_priorities_were_stated(self, client) -> None:
        events = await _turn(client, "v11-priorities-skip", {"message": _FLIGHTS_WITH_PRIORITY})
        plan = _plan_of(events)
        assert plan["root"]["type"] == "product_grid"

    async def test_skipped_on_followup_turns(self, client) -> None:
        session = "v11-priorities-fu"
        await _turn(client, session, {"message": _FLIGHTS_WITH_PRIORITY})
        # A follow-up rides the proceed pipeline even without stated priorities
        # beyond the first message's.
        events = await _turn(client, session, {"message": "compare the first two"})
        plan = _plan_of(events)
        assert plan["root"]["type"] == "comparison_table"


class TestRefineLoop:
    async def test_sort_chip_reranks_and_echoes_state(self, client) -> None:
        session = "v11-refine-sort"
        events1 = await _turn(client, session, {"message": _FLIGHTS_WITH_PRIORITY})
        plan1 = _plan_of(events1)
        assert plan1["root"]["props"]["refinement"]["sort"] == "relevance"

        chip = next(
            action
            for action in plan1["root"]["actions"]
            if action["type"] == "refine" and action["payload"].get("sort") == "price_asc"
        )
        events2 = await _turn(client, session, {"ui_action": chip})
        plan2 = _plan_of(events2)
        assert plan2["root"]["props"]["refinement"] == {
            "sort": "price_asc",
            "filters": {},
        }
        # Deterministic price-ascending order over the presented set.
        catalog = {product.id: product for product in load_catalog()}
        ids = plan2["root"]["props"]["productIds"]
        prices = [catalog[pid].price_usd for pid in ids]
        assert prices == sorted(prices)
        # The active chip is gone; a Clear chip appeared.
        refine_labels = [
            action["label"] for action in plan2["root"]["actions"] if action["type"] == "refine"
        ]
        assert "Price: low to high" not in refine_labels
        assert "Clear refinements" in refine_labels
        assert events2[-1][0] == "turn_end"

    async def test_filter_chip_and_clear(self, client) -> None:
        session = "v11-refine-filter"
        events1 = await _turn(client, session, {"message": _FLIGHTS_WITH_PRIORITY})
        plan1 = _plan_of(events1)
        anc_chip = next(
            action
            for action in plan1["root"]["actions"]
            if action["type"] == "refine" and action["payload"].get("ancOnly")
        )
        events2 = await _turn(client, session, {"ui_action": anc_chip})
        plan2 = _plan_of(events2)
        assert plan2["root"]["props"]["refinement"]["filters"]["ancOnly"] is True

        clear = next(
            action
            for action in plan2["root"]["actions"]
            if action["type"] == "refine" and action["label"] == "Clear refinements"
        )
        events3 = await _turn(client, session, {"ui_action": clear})
        plan3 = _plan_of(events3)
        assert plan3["root"]["props"]["refinement"] == {"sort": "relevance", "filters": {}}

    async def test_chip_turn_makes_no_intent_model_call(self, client, fake_llm_factory) -> None:
        fake = fake_llm_factory([])
        session = "v11-refine-calls"
        await _turn(client, session, {"message": _FLIGHTS_WITH_PRIORITY})
        calls_after_first = list(fake.calls)

        await _turn(
            client,
            session,
            {
                "ui_action": {
                    "type": "refine",
                    "label": "Top rated",
                    "payload": {"sort": "rating"},
                }
            },
        )
        new_calls = fake.calls[len(calls_after_first) :]
        # The weights call still runs (ranked stays fresh); the intent call
        # never does on a chip turn.
        assert [schema for schema, _index in new_calls] == ["PreferenceWeights", "Narration"]


class TestCartSteppers:
    async def test_step_updates_line_and_amends_the_anchor(self, client) -> None:
        session = "v11-stepper-01"
        await _turn(client, session, {"message": _FLIGHTS_WITH_PRIORITY})
        events2 = await _turn(client, session, {"message": "add the first one to my cart"})
        plan2 = _plan_of(events2)
        assert plan2["root"]["props"]["items"] == [
            {"productId": plan2["root"]["props"]["items"][0]["productId"], "quantity": 1}
        ]
        steps = [a for a in plan2["root"]["actions"] if a["type"] == "set_quantity"]
        assert [(s["label"], s["payload"]["quantity"]) for s in steps] == [("+", 2)]

        plus = steps[0]
        events3 = await _turn(client, session, {"ui_action": plus})
        plan3 = _plan_of(events3)
        assert plan3["amendsTurnId"] == plan2["turnId"]
        assert plan3["root"]["props"]["items"][0]["quantity"] == 2
        steps3 = [a for a in plan3["root"]["actions"] if a["type"] == "set_quantity"]
        assert [(s["label"], s["payload"]["quantity"]) for s in steps3] == [("−", 1), ("+", 3)]
        text3 = "".join(d["text"] for name, d in events3 if name == "message_delta")
        assert "set to 2" in text3
