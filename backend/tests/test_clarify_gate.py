"""US2 rule-table unit tests: clarify gate + ask node (research R7).

The routing function is pure, so the exhaustive rule table is exercised
directly with synthetic state dicts — no LLM, no graph. The ``ui_agent_ask``
node runs both directly (stream-writer no-ops outside a graph run) and
through the compiled graph; the budget-default and contradiction policies of
``search_node`` run through full graph invokes in mock mode (deterministic).
"""

from __future__ import annotations

import pytest

from app.catalog.loader import load_catalog
from app.dsl.models import UIPlan
from app.dsl.validate import serialize_plan, validate_plan
from app.graph.builder import get_graph
from app.graph.nodes import ASK_QUESTION, DEFAULT_BUDGET_USD, clarify_decision, ui_agent_ask

pytestmark = pytest.mark.usefixtures("mock_settings")


def _invoke(session_id: str, message: str):
    """One full turn on a fresh thread; returns (final state, config)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    state = graph.invoke(
        {
            "pending_user_text": message,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    return state, config


# ---------------------------------------------------------------------------
# Rule table: clarify_decision (pure router)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({}, "ask"),  # no intent at all
        ({"intent": {}}, "ask"),  # intent present, category missing
        ({"intent": {"category": None}}, "ask"),
        ({"intent": {"category": "laptops"}}, "ask"),  # not a catalog category
        ({"intent": {"category": "headphones"}}, "proceed"),  # known category
        ({"intent": {"category": "Headphones"}}, "proceed"),  # case-insensitive
        ({"intent": {"category": "  HEADPHONES "}}, "proceed"),  # whitespace + case
        # Rule 1 outranks rule 2: never ask twice in a row.
        ({"asked_clarification": True}, "proceed"),
        ({"asked_clarification": True, "intent": {"category": "laptops"}}, "proceed"),
        ({"asked_clarification": True, "intent": {}}, "proceed"),
        # Budget/contradiction states never ask (R7: don't ask about budget).
        ({"intent": {"category": "headphones", "budget_usd": None}}, "proceed"),
        ({"intent": {"category": "headphones", "flag_contradiction": True}}, "proceed"),
    ],
)
def test_clarify_decision_rule_table(state: dict, expected: str) -> None:
    assert clarify_decision(state) == expected


def test_clarify_decision_is_pure() -> None:
    """Same input → same answer, and the input dict is never mutated."""
    state = {"intent": {"category": "laptops"}, "asked_clarification": False}
    assert clarify_decision(state) == clarify_decision(state) == "ask"
    assert state == {"intent": {"category": "laptops"}, "asked_clarification": False}


def test_rule_table_tracks_the_real_catalog_categories() -> None:
    """A category is 'known' exactly when the loaded catalog carries it."""
    catalog_categories = {product.category.lower() for product in load_catalog()}
    assert catalog_categories  # sanity: the catalog is non-empty
    for category in catalog_categories:
        assert clarify_decision({"intent": {"category": category.upper()}}) == "proceed"
    assert clarify_decision({"intent": {"category": "televisions"}}) == "ask"


# ---------------------------------------------------------------------------
# ui_agent_ask: the node function (direct invocation, no stream context)
# ---------------------------------------------------------------------------


def test_ask_node_builds_valid_picker_and_flips_flag() -> None:
    state = {"session_id": "gate-direct-01", "turn_id": 0, "intent": {}, "messages": []}
    update = ui_agent_ask(state)

    assert update["asked_clarification"] is True
    assert update["turn_id"] == 1
    assert update.get("error") is None

    plan = UIPlan.model_validate(update["plan"])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.session_id == "gate-direct-01"
    assert plan.turn_id == 1
    assert plan.root.type == "preference_picker"
    assert plan.root.props.question == ASK_QUESTION

    # Chips: catalog categories (title-cased) + "Something else", capped at 4.
    catalog_categories = sorted({p.category for p in load_catalog()})
    expected_labels = [category.replace("_", " ").title() for category in catalog_categories]
    assert plan.root.props.options == [*expected_labels, "Something else"]

    # Every option wired to a select_preference action with a slug payload.
    by_label = {action.label: action.payload.get("value") for action in plan.root.actions}
    assert by_label["Something else"] == "other"
    for label, value in zip(expected_labels, catalog_categories, strict=True):
        assert by_label[label] == value

    # Assistant question appended to the transcript.
    assert update["messages"][-1]["role"] == "assistant"
    assert ASK_QUESTION in update["messages"][-1]["content"]

    # The stored dict is exactly the validated wire document (camelCase).
    assert update["plan"] == serialize_plan(plan)


def test_ask_node_respects_the_four_option_cap() -> None:
    state = {"session_id": "gate-direct-02", "turn_id": 3, "messages": []}
    update = ui_agent_ask(state)
    assert len(update["plan"]["root"]["props"]["options"]) <= 4


# ---------------------------------------------------------------------------
# Ask turn through the compiled graph (mock mode)
# ---------------------------------------------------------------------------


async def test_ask_turn_streams_question_and_picker_then_ends() -> None:
    graph = get_graph()
    session_id = "gate-ask-001"
    config = {"configurable": {"thread_id": session_id}}
    events: list[tuple[str, dict]] = []
    async for payload in graph.astream(
        {
            "pending_user_text": "Help me pick a gift.",
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
        stream_mode="custom",
    ):
        kind, data = payload
        events.append((kind, data))

    kinds = [kind for kind, _data in events]
    statuses = [data["stage"] for kind, data in events if kind == "status"]
    # The ask turn has intent run, then ONLY the question + picker: no search
    # stages, and the turn ends right after the ask node.
    assert statuses == ["intent_parsed"]
    assert kinds.count("message_delta") >= 1
    question = "".join(data["text"] for kind, data in events if kind == "message_delta")
    assert ASK_QUESTION in question
    assert kinds.count("ui_update") == 1
    assert kinds[-1] == "ui_update"  # routes appends turn_end after the stream

    plan_dict = next(data for kind, data in events if kind == "ui_update")
    plan = UIPlan.model_validate(plan_dict)
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.root.type == "preference_picker"

    state = graph.get_state(config).values
    assert state["asked_clarification"] is True
    assert state["plan"]["root"]["type"] == "preference_picker"
    assert state["turn_id"] == 1
    assert [message["role"] for message in state["messages"]] == ["user", "assistant"]


async def test_asked_clarification_forces_proceed_on_unknown_category() -> None:
    """After the ask turn, an unknown category never triggers a second ask."""
    graph = get_graph()
    session_id = "gate-ask-002"
    config = {"configurable": {"thread_id": session_id}}
    graph.invoke(
        {
            "pending_user_text": "Help me pick a gift.",
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    state = graph.invoke(
        {
            "pending_user_text": "actually laptops",
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    assert state["asked_clarification"] is True
    # Completed to a plan (closest matches over the whole catalog), not a
    # second question.
    assert state["plan"]["root"]["type"] == "product_grid"
    assert state["ranked"]
    assert state.get("error") is None


# ---------------------------------------------------------------------------
# Budget default + contradiction policies (R7, via full graph invokes)
# ---------------------------------------------------------------------------


def test_missing_budget_proceeds_with_default_cap_and_disclosure() -> None:
    state, _config = _invoke(
        "gate-budget-001",
        "I want headphones for long flights. Noise cancellation and comfort matter most.",
    )
    assert state.get("error") is None
    assert state["intent"]["budget_usd"] == DEFAULT_BUDGET_USD
    assumptions = state["intent"]["assumptions"]
    assert any("$250" in item and "cap" in item for item in assumptions)
    catalog = {product.id: product for product in load_catalog()}
    assert state["ranked"]
    assert all(
        catalog[scored.product_id].price_usd <= DEFAULT_BUDGET_USD for scored in state["ranked"]
    )


def test_budget_assumption_is_not_duplicated_across_turns() -> None:
    graph = get_graph()
    session_id = "gate-budget-002"
    config = {"configurable": {"thread_id": session_id}}
    for _ in range(2):
        state = graph.invoke(
            {
                "pending_user_text": "I want headphones for long flights.",
                "pending_ui_action": None,
                "session_id": session_id,
            },
            config=config,
        )
    assumptions = state["intent"]["assumptions"]
    assert sum(1 for item in assumptions if "$250" in item) == 1


def test_contradiction_flags_discloses_and_falls_back() -> None:
    message = "noise cancelling headphones under $40 with 60 hour battery and ldac"
    state, _config = _invoke("gate-contradiction-001", message)
    assert state.get("error") is None
    assert state["intent"]["flag_contradiction"] is True
    assumptions = state["intent"]["assumptions"]
    assert any("isn't available" in item for item in assumptions)
    # Fallback set: ranked non-empty, within the known category.
    assert len(state["ranked"]) >= 3
    catalog = {product.id: product for product in load_catalog()}
    assert all(catalog[scored.product_id].category == "headphones" for scored in state["ranked"])
