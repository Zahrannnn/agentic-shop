"""Graph-level happy-path, determinism, and relaxation tests (mock mode).

Runs the compiled backbone directly (``get_graph().invoke`` / ``astream``)
without HTTP: ranking correctness for the canonical flights request, the
contract status-stage order, SC-002 byte-identical rankings across fresh
sessions, plan validation against the DSL, monotonic ``turn_id``, and the
empty-search relaxation disclosure.

The US2/US3 section covers the clarify gate end-to-end: exactly one ask turn
with a validated preference picker, completion after the answer with no
second question, the stated default-budget assumption, and the contradiction
fallback (spec acceptance scenarios 1-4).

The US4 section covers multi-turn follow-ups: deterministic resolution of
positional/demonstrative references, comparison/details/cart plans, the
clean no-products disclosure, the preference re-rank pipeline, and the
one-LLM-call guarantee. The US5 section covers fault injection through the
scripted fake (single retry / single clean error / no leakage) and
cross-session determinism of rankings and narration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.api.schemas import STAGE_ORDER
from app.catalog.loader import load_catalog
from app.dsl.models import UIPlan
from app.dsl.validate import serialize_plan, validate_plan
from app.graph.builder import get_graph
from app.graph.nodes import NO_PRODUCTS_DISCLOSURE
from app.graph.schemas import PreferenceWeights
from app.llm.client import _JSON_MODE_MODELS, StructuredOutputError, call_structured
from app.ranking.scorer import score_products

pytestmark = pytest.mark.usefixtures("mock_settings")

FLIGHTS_MESSAGE: str = (
    "Help me find the best headphones for long flights under $200. "
    "Noise cancellation and comfort matter most."
)

#: US2: a request without any recognizable category.
GIFT_MESSAGE: str = "Help me pick a gift."

#: US2: contradictory constraints — no catalog product satisfies them at any
#: price (both >=60h headphones lack ldac and nothing costs under $49).
CONTRA_MESSAGE: str = "noise cancelling headphones under $40 with 60 hour battery and ldac"

ASK_QUESTION: str = "Which category are you shopping for?"

FIXTURES_DIR: Path = Path(__file__).resolve().parent.parent / "fixtures" / "ui-plans"

#: Deterministic mock-mode podium for the flights request. NOTE: the
#: ``product-grid-flights`` fixture lists ``skyline-hush`` third, but the pure
#: scorer with the mock's anc/comfort weights (1.0 / 0.8) deterministically
#: ranks ``maple-ridge-comfort-150`` there; the fixture-vs-ranking discrepancy
#: is reported to the owner (the scorer and mock handlers are binding).
EXPECTED_TOP3: list[str] = ["aurora-hush-pro", "cloudline-air", "maple-ridge-comfort-150"]


def _run_graph(session_id: str, message: str = FLIGHTS_MESSAGE):
    """Invoke one full turn on a fresh thread; returns (final state, config)."""
    graph: CompiledStateGraph = get_graph()
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


def test_flights_request_ranks_aurora_hush_pro_first() -> None:
    state, _config = _run_graph("graph-rank-001")
    ranked = state["ranked"]
    assert ranked, "expected a non-empty ranking"
    assert ranked[0].product_id == "aurora-hush-pro"

    catalog = {product.id: product for product in load_catalog()}
    assert all(catalog[scored.product_id].price_usd <= 200.0 for scored in ranked)
    assert state.get("error") is None


async def test_status_events_follow_contract_order() -> None:
    graph: CompiledStateGraph = get_graph()
    session_id = "graph-order-001"
    events: list[tuple[str, dict[str, object]]] = []
    async for payload in graph.astream(
        {
            "pending_user_text": FLIGHTS_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config={"configurable": {"thread_id": session_id}},
        stream_mode="custom",
    ):
        kind, data = payload
        events.append((kind, data))

    stages = [data["stage"] for kind, data in events if kind == "status"]
    assert stages == list(STAGE_ORDER)


def test_ranking_is_identical_across_fresh_sessions() -> None:
    """SC-002: same request, fresh sessions -> identical ranking, byte-stable."""

    def signature(session_id: str) -> list[tuple[str, float]]:
        state, _config = _run_graph(session_id)
        return [(scored.product_id, round(scored.score, 10)) for scored in state["ranked"]]

    assert signature("graph-det-aaa") == signature("graph-det-bbb")


def test_plan_validates_against_dsl_and_catalog() -> None:
    state, _config = _run_graph("graph-plan-001")
    plan_dict = state["plan"]
    assert plan_dict is not None

    plan = UIPlan.model_validate(plan_dict)
    validate_plan(plan, {product.id for product in load_catalog()})
    # The stored dict must be exactly the validated wire document.
    assert plan_dict == serialize_plan(plan)

    assert plan.session_id == "graph-plan-001"
    assert plan.turn_id == 1
    assert plan.root.type == "product_grid"
    props = plan.root.props
    assert props.ranked is True
    assert props.product_ids == EXPECTED_TOP3
    assert [action.type for action in plan.root.actions] == [
        "compare",
        "details",
        "add_to_cart",
    ]


def test_turn_id_is_monotonic_across_turns() -> None:
    state_first, config = _run_graph("graph-turn-0001")
    assert state_first["plan"]["turnId"] == 1

    graph: CompiledStateGraph = get_graph()
    state_second = graph.invoke(
        {
            "pending_user_text": FLIGHTS_MESSAGE,
            "pending_ui_action": None,
            "session_id": "graph-turn-0001",
        },
        config=config,
    )
    assert state_second["plan"]["turnId"] == 2
    roles = [message["role"] for message in state_second["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_empty_results_relax_budget_and_disclose_assumption() -> None:
    state, _config = _run_graph("graph-relax-01", "I need headphones under $10.")
    assert state["candidates"], "relaxation must yield closest matches"
    assumptions = state["intent"]["assumptions"]
    assert any("relaxed the price cap" in item for item in assumptions)
    catalog = {product.id: product for product in load_catalog()}
    # The disclosed relaxation is the first +$50 step: the $10 cap became $60.
    assert all(catalog[scored.product_id].price_usd <= 60.0 for scored in state["ranked"])


# ---------------------------------------------------------------------------
# US2: clarify gate — acceptance scenarios 1-4
# ---------------------------------------------------------------------------


async def _collect_stream(session_id: str, message: str, ui_action: dict | None = None):
    """Stream one turn; returns (events, final checkpointed state, config)."""
    graph: CompiledStateGraph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    events: list[tuple[str, dict]] = []
    async for payload in graph.astream(
        {
            "pending_user_text": message,
            "pending_ui_action": ui_action,
            "session_id": session_id,
        },
        config=config,
        stream_mode="custom",
    ):
        kind, data = payload
        events.append((kind, data))
    state = graph.get_state(config).values
    return events, state, config


async def test_us2_category_less_request_asks_exactly_once() -> None:
    """Acceptance 1: exactly one question with chips, then the turn ends."""
    events, state, _config = await _collect_stream("us2-scenario-001", GIFT_MESSAGE)

    kinds = [kind for kind, _data in events]
    statuses = [data["stage"] for kind, data in events if kind == "status"]
    assert statuses == ["intent_parsed"]  # no search stages on the ask turn

    assert kinds.count("message_delta") >= 1
    question = "".join(data["text"] for kind, data in events if kind == "message_delta")
    assert ASK_QUESTION in question

    updates = [data for kind, data in events if kind == "ui_update"]
    assert len(updates) == 1
    plan = UIPlan.model_validate(updates[0])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.root.type == "preference_picker"
    assert plan.root.props.question == ASK_QUESTION

    assert state["asked_clarification"] is True
    assert kinds[-1] == "ui_update"  # routes adds the turn_end terminator


async def test_us2_answer_completes_without_second_question() -> None:
    """Acceptance 2: after the answer, the pipeline runs to recommendation."""
    graph: CompiledStateGraph = get_graph()
    session_id = "us2-scenario-002"
    config = {"configurable": {"thread_id": session_id}}

    first = graph.invoke(
        {
            "pending_user_text": GIFT_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    assert first["plan"]["root"]["type"] == "preference_picker"

    # The answer is the full flights request: the outcome must be consistent
    # with the US1 podium (top pick identical).
    second = graph.invoke(
        {
            "pending_user_text": FLIGHTS_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    assert second.get("error") is None
    assert second["asked_clarification"] is True  # asked once, never again
    assert second["plan"]["root"]["type"] == "product_grid"
    assert second["ranked"][0].product_id == EXPECTED_TOP3[0]
    assert [message["role"] for message in second["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    # Same two-turn conversation streamed: the answer turn carries the full
    # status lifecycle and its plan is the grid (no second question).
    events, _state, _config = await _collect_stream("us2-scenario-002b", FLIGHTS_MESSAGE)
    statuses = [data["stage"] for kind, data in events if kind == "status"]
    assert statuses == list(STAGE_ORDER)
    grid_updates = [
        data
        for kind, data in events
        if kind == "ui_update" and data["root"]["type"] != "product_grid"
    ]
    assert grid_updates == []


async def test_us2_chip_answer_skips_intent_llm_and_completes(monkeypatch) -> None:
    """A category chip IS the intent: the LLM intent call is skipped."""

    class _RecordingFake:
        """Minimal fake LLM: replays one canned payload per schema, in order.

        ``with_structured_output`` returns a bound object with ``invoke`` —
        the exact surface ``call_structured`` consumes.
        """

        def __init__(self, payloads: list[dict]) -> None:
            self._payloads = list(payloads)
            self.schemas: list[str] = []

        def with_structured_output(self, schema: type) -> object:
            outer = self

            class _Bound:
                def invoke(self, _messages: object) -> object:
                    outer.schemas.append(schema.__name__)
                    return outer._payloads.pop(0)

            return _Bound()

    fake = _RecordingFake(
        [
            {"anc": 0.0, "comfort": 0.0, "battery": 0.0, "sound": 0.0, "value": 0.0},
            {"intro": "Here are some options.", "per_product": [], "outro": "Want more?"},
        ]
    )

    graph: CompiledStateGraph = get_graph()
    session_id = "us2-chip-001"
    config = {"configurable": {"thread_id": session_id}}
    # Ask turn first, with the normal mock LLM (its intent call is not under
    # test); the recording fake is armed only for the chip answer turn.
    graph.invoke(
        {
            "pending_user_text": GIFT_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    # Nodes bind get_llm via from-import, so patch the name where it is used.
    import app.graph.nodes as graph_nodes

    monkeypatch.setattr(graph_nodes, "get_llm", lambda: fake)
    state = graph.invoke(
        {
            "pending_user_text": "",
            "pending_ui_action": {
                "type": "select_preference",
                "label": "Headphones",
                "payload": {"value": "headphones"},
            },
            "session_id": session_id,
        },
        config=config,
    )
    # Exactly the two post-intent calls ran: IntentExtraction was skipped, and
    # plan assembly is code-owned (no PlanSelection call exists anymore).
    assert fake.schemas == ["PreferenceWeights", "Narration"]
    assert state["intent"]["category"] == "headphones"
    assert state["plan"]["root"]["type"] == "product_grid"
    assert state.get("error") is None


def test_us2_budget_less_request_completes_with_stated_assumption() -> None:
    """Acceptance 3: no budget → sensible cap applied and openly stated."""
    state, _config = _run_graph(
        "us2-scenario-003",
        "I want headphones for long flights. Noise cancellation and comfort matter most.",
    )
    assert state.get("error") is None
    assert state["intent"]["budget_usd"] == 250.0
    assumptions = state["intent"]["assumptions"]
    assert any("$250" in item for item in assumptions)

    catalog = {product.id: product for product in load_catalog()}
    assert all(catalog[scored.product_id].price_usd <= 250.0 for scored in state["ranked"])

    # The assumption is disclosed in the streamed answer text.
    assistant = [message for message in state["messages"] if message["role"] == "assistant"]
    assert assistant
    assert assistant[-1]["content"].startswith("Note: ")
    assert "$250" in assistant[-1]["content"]


def test_us2_contradictory_request_presents_closest_matches() -> None:
    """Acceptance 4: contradiction flag + honest disclosure, still completes."""
    state, _config = _run_graph("us2-scenario-004", CONTRA_MESSAGE)
    assert state.get("error") is None
    assert state["intent"]["flag_contradiction"] is True
    assumptions = state["intent"]["assumptions"]
    assert any("isn't available" in item for item in assumptions)

    assert state["ranked"], "closest matches must be presented"
    catalog = {product.id: product for product in load_catalog()}
    assert all(catalog[scored.product_id].category == "headphones" for scored in state["ranked"])

    assistant = [message for message in state["messages"] if message["role"] == "assistant"]
    assert assistant
    assert "Note:" in assistant[-1]["content"]
    assert "isn't available" in assistant[-1]["content"]


def test_us2_other_chip_searches_whole_catalog_and_discloses() -> None:
    """'Something else' → category stays open, whole catalog, disclosed."""
    graph: CompiledStateGraph = get_graph()
    session_id = "us2-other-001"
    config = {"configurable": {"thread_id": session_id}}
    graph.invoke(
        {
            "pending_user_text": GIFT_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    state = graph.invoke(
        {
            "pending_user_text": "",
            "pending_ui_action": {
                "type": "select_preference",
                "label": "Something else",
                "payload": {"value": "other"},
            },
            "session_id": session_id,
        },
        config=config,
    )
    assert state.get("error") is None
    assert state["intent"]["category"] is None
    assert state["ranked"]
    assert any("whole catalog" in item for item in state["intent"]["assumptions"])
    assert state["plan"]["root"]["type"] == "product_grid"


# ---------------------------------------------------------------------------
# US3: every turn carries a validated plan
# ---------------------------------------------------------------------------


def test_us3_ask_plan_matches_preference_picker_fixture() -> None:
    state, _config = _run_graph("us3-picker-001", GIFT_MESSAGE)
    plan_dict = state["plan"]
    plan = UIPlan.model_validate(plan_dict)
    validate_plan(plan, {product.id for product in load_catalog()})

    fixture = json.loads(
        (FIXTURES_DIR / "preference-picker-category.json").read_text(encoding="utf-8")
    )
    # Multi-category catalog (D5 amendment): the generated chips now cover
    # every catalog category plus the fallback, so the headphones-era contract
    # fixture is a strict SUBSET of the generated picker, not equal to it.
    assert plan.root.props.question == fixture["root"]["props"]["question"]
    assert fixture["root"]["props"]["options"] == ["Headphones", "Something else"]
    generated_options = plan.root.props.options
    assert all(option in generated_options for option in fixture["root"]["props"]["options"])
    catalog_categories = sorted({p.category for p in load_catalog()})
    assert generated_options == [
        *[category.replace("_", " ").title() for category in catalog_categories],
        "Something else",
    ]
    generated_actions = [
        {"type": action.type, "label": action.label, "payload": action.payload}
        for action in plan.root.actions
    ]
    for fixture_action in fixture["root"]["actions"]:
        assert fixture_action in generated_actions
    assert len(generated_actions) == len(generated_options)
    assert plan_dict["planVersion"] == fixture["planVersion"] == "1"
    assert plan_dict["root"]["type"] == fixture["root"]["type"]


def test_us3_turn_id_is_monotonic_ask_then_answer() -> None:
    state_first, config = _run_graph("us3-turn-001", GIFT_MESSAGE)
    assert state_first["plan"]["turnId"] == 1

    graph: CompiledStateGraph = get_graph()
    state_second = graph.invoke(
        {
            "pending_user_text": FLIGHTS_MESSAGE,
            "pending_ui_action": None,
            "session_id": "us3-turn-001",
        },
        config=config,
    )
    assert state_second["plan"]["turnId"] == 2


def test_us3_answer_plan_validates_and_replaces_ask_plan() -> None:
    """The second turn's plan is a full standalone document (D2)."""
    graph: CompiledStateGraph = get_graph()
    session_id = "us3-fullreplace-001"
    config = {"configurable": {"thread_id": session_id}}
    first = graph.invoke(
        {
            "pending_user_text": GIFT_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    second = graph.invoke(
        {
            "pending_user_text": FLIGHTS_MESSAGE,
            "pending_ui_action": None,
            "session_id": session_id,
        },
        config=config,
    )
    plan = UIPlan.model_validate(second["plan"])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert second["plan"] == serialize_plan(plan)
    assert plan.session_id == session_id
    assert plan.turn_id == 2
    assert plan.root.type == "product_grid"
    # Full replace: the stored plan no longer contains the picker.
    assert second["plan"]["root"]["type"] != first["plan"]["root"]["type"]
    assert second["selected_ids"] == [scored.product_id for scored in second["ranked"][:3]]


# ---------------------------------------------------------------------------
# US4: multi-turn follow-ups in one session (pure resolver unit tests live
# in tests/test_followups.py)
# ---------------------------------------------------------------------------


async def test_us4_compare_first_two_produces_comparison_table() -> None:
    """Acceptance 1: "compare the first two" compares the previous top two."""
    _state1, _config = _run_graph("us4-compare-001")
    events, state, _config = await _collect_stream("us4-compare-001", "compare the first two")

    kinds = [kind for kind, _data in events]
    updates = [data for kind, data in events if kind == "ui_update"]
    assert len(updates) == 1
    plan = UIPlan.model_validate(updates[0])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.turn_id == 2
    assert plan.root.type == "comparison_table"
    assert plan.root.props.product_ids == EXPECTED_TOP3[:2]

    fixture = json.loads((FIXTURES_DIR / "comparison-two.json").read_text(encoding="utf-8"))
    assert plan.root.props.attributes == fixture["root"]["props"]["attributes"]
    assert [action.type for action in plan.root.actions] == ["choose"]
    action = plan.root.actions[0]
    assert action.payload == {"productId": EXPECTED_TOP3[0]}
    catalog = {product.id: product for product in load_catalog()}
    assert action.label == f"Choose {catalog[EXPECTED_TOP3[0]].name}"

    text = "".join(data["text"] for kind, data in events if kind == "message_delta")
    assert text == (
        f"Here's the side-by-side comparison of "
        f"{catalog[EXPECTED_TOP3[0]].name} and {catalog[EXPECTED_TOP3[1]].name}."
    )
    assert state["selected_ids"] == EXPECTED_TOP3[:2]
    assert state.get("error") is None
    assert state.get("followup") is not None  # last write wins per turn
    # Raw graph stream: ui_plan emits before respond, so the last payload is
    # a delta (routes defers the ui frame for the contract wire order).
    assert kinds[-1] == "message_delta"
    assert "error" not in kinds


async def test_us4_details_follow_up_shows_product_details() -> None:
    """'tell me more about the second one' -> product_details with quotes."""
    _state1, _config = _run_graph("us4-details-001")
    _events, state, _config = await _collect_stream(
        "us4-details-001", "tell me more about the second one"
    )
    updates = [data for kind, data in _events if kind == "ui_update"]
    assert len(updates) == 1
    plan = UIPlan.model_validate(updates[0])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.root.type == "product_details"
    assert plan.root.props.product_id == EXPECTED_TOP3[1]
    assert plan.root.props.show_quotes is True
    assert plan.root.actions == []

    catalog = {product.id: product for product in load_catalog()}
    text = "".join(data["text"] for kind, data in _events if kind == "message_delta")
    assert text == f"Here's more about {catalog[EXPECTED_TOP3[1]].name}."
    assert state["selected_ids"] == [EXPECTED_TOP3[1]]


async def test_us4_add_view_remove_cart_round_trip() -> None:
    """Acceptance 3: add -> confirm with cart plan -> view -> remove reverses."""
    session = "us4-cart-001"
    _state1, _config = _run_graph(session)
    catalog = {product.id: product for product in load_catalog()}
    top = catalog[EXPECTED_TOP3[0]]

    _events, state2, _config = await _collect_stream(session, "add the first one to my cart")
    assert state2["cart"] == [{"product_id": EXPECTED_TOP3[0], "quantity": 1}]
    plan2 = UIPlan.model_validate(state2["plan"])
    validate_plan(plan2, set(catalog))
    assert plan2.root.type == "cart_view"
    assert plan2.root.props.model_dump(by_alias=True, exclude_none=True) == {
        "items": [{"productId": EXPECTED_TOP3[0], "quantity": 1}],
        "totalUsd": top.price_usd,
    }
    assert [(a.type, a.payload) for a in plan2.root.actions] == [
        ("remove_from_cart", {"productId": EXPECTED_TOP3[0]})
    ]
    text2 = "".join(d["text"] for k, d in _events if k == "message_delta")
    assert text2 == f"Added {top.name} to your cart."

    _events, state3, _config = await _collect_stream(session, "what's in my cart?")
    assert state3["cart"] == [{"product_id": EXPECTED_TOP3[0], "quantity": 1}]
    assert state3["plan"]["root"]["type"] == "cart_view"
    # The explicit cart view amends the anchored region too (single cart
    # section on the client) instead of appending a duplicate table.
    assert state3["plan"]["amendsTurnId"] == state2["cart_plan_turn_id"]
    text3 = "".join(d["text"] for k, d in _events if k == "message_delta")
    assert text3 == f"Your cart: {top.name} x1 — total ${top.price_usd:g}."

    _events, state4, _config = await _collect_stream(session, "remove the first one from my cart")
    assert state4["cart"] == []
    assert state4["plan"]["root"]["type"] == "cart_view"
    assert state4["plan"]["amendsTurnId"] == state2["cart_plan_turn_id"]
    assert state4["plan"]["root"]["props"] == {"items": [], "totalUsd": 0.0}
    text4 = "".join(d["text"] for k, d in _events if k == "message_delta")
    assert text4 == f"Removed {top.name} from your cart."


async def test_us4_second_cart_mutation_amends_the_first_cart_turn() -> None:
    """D2 amendment: the first cart mutation emits a standalone ``cart_view``
    (no ``amendsTurnId``) and anchors ``cart_plan_turn_id``; the next cart
    mutation emits a ``cart_view`` whose ``amendsTurnId`` points at that
    anchor while its own ``turnId`` keeps incrementing (the id identifies the
    turn, not the plan region)."""
    session = "us4-amend-001"
    _state1, _config = _run_graph(session)
    catalog_ids = {product.id for product in load_catalog()}

    _events2, state2, _config = await _collect_stream(session, "add the first one to my cart")
    plan2 = UIPlan.model_validate(state2["plan"])
    assert plan2.root.type == "cart_view"
    assert plan2.amends_turn_id is None
    assert "amendsTurnId" not in state2["plan"]  # absent from the wire document
    assert state2["cart_plan_turn_id"] == plan2.turn_id

    _events3, state3, _config = await _collect_stream(session, "add the second one to my cart")
    plan3 = UIPlan.model_validate(state3["plan"])
    validate_plan(plan3, catalog_ids)
    assert plan3.root.type == "cart_view"
    assert plan3.amends_turn_id == plan2.turn_id
    assert state3["plan"]["amendsTurnId"] == plan2.turn_id  # on the wire, camelCase
    assert plan3.turn_id == plan2.turn_id + 1
    assert state3["cart_plan_turn_id"] == plan2.turn_id  # anchor unchanged
    assert {line.product_id: line.quantity for line in plan3.root.props.items} == {
        EXPECTED_TOP3[0]: 1,
        EXPECTED_TOP3[1]: 1,
    }


async def test_us4_add_that_one_targets_last_selected() -> None:
    """Prescribed semantics: "that one" is the last selected id (third pick
    after a plain recommendation, i.e. the tail of selected_ids)."""
    session = "us4-thatone-001"
    _state1, _config = _run_graph(session)
    _events, state, _config = await _collect_stream(session, "add that one to my cart")
    assert state["cart"] == [{"product_id": EXPECTED_TOP3[2], "quantity": 1}]


async def test_us4_compare_without_products_discloses_cleanly() -> None:
    """A follow-up with nothing presented ends cleanly: one disclosure delta +
    a text_block plan — no error frame, no search stages."""
    events, state, _config = await _collect_stream("us4-disclose-001", "compare the first two")
    kinds = [kind for kind, _data in events]
    statuses = [data["stage"] for kind, data in events if kind == "status"]
    # The disclose route skips search/research/recommend entirely so their
    # budget/category defaults cannot record spurious session assumptions.
    assert statuses == ["intent_parsed", "building_ui"]
    text = "".join(data["text"] for kind, data in events if kind == "message_delta")
    assert text == NO_PRODUCTS_DISCLOSURE
    updates = [data for kind, data in events if kind == "ui_update"]
    assert len(updates) == 1
    plan = UIPlan.model_validate(updates[0])
    validate_plan(plan, {product.id for product in load_catalog()})
    assert plan.root.type == "text_block"
    assert plan.root.props.body == NO_PRODUCTS_DISCLOSURE
    # Raw graph stream order: ui_update (ui_plan) then the disclosure delta
    # (respond); routes defers the ui frame to keep the wire order.
    assert kinds[-1] == "message_delta"
    assert "error" not in kinds
    assert state.get("error") is None


async def test_us4_choose_action_shows_details() -> None:
    """The comparison table's choose action resolves to a details turn."""
    session = "us4-choose-001"
    _state1, _config = _run_graph(session)
    _events, state, _config = await _collect_stream(
        session,
        "",
        ui_action={
            "type": "choose",
            "label": "Choose Cloudline Air",
            "payload": {"productId": EXPECTED_TOP3[1]},
        },
    )
    plan = UIPlan.model_validate(state["plan"])
    assert plan.root.type == "product_details"
    assert plan.root.props.product_id == EXPECTED_TOP3[1]
    catalog = {product.id: product for product in load_catalog()}
    text = "".join(d["text"] for k, d in _events if k == "message_delta")
    assert text == f"Here's more about {catalog[EXPECTED_TOP3[1]].name}."


async def test_us4_add_action_with_payload_updates_cart() -> None:
    """A grid add_to_cart action with an explicit productId adds that product."""
    session = "us4-addaction-001"
    _state1, _config = _run_graph(session)
    _events, state, _config = await _collect_stream(
        session,
        "",
        ui_action={
            "type": "add_to_cart",
            "label": "Add to cart",
            "payload": {"productId": EXPECTED_TOP3[0]},
        },
    )
    assert state["cart"] == [{"product_id": EXPECTED_TOP3[0], "quantity": 1}]
    assert state["plan"]["root"]["type"] == "cart_view"


async def test_us4_preference_rerank_flows_through_normal_pipeline() -> None:
    """Acceptance 2: a changed priority re-scores through intent -> weights ->
    pure scorer (never a fast path), and the plan is a fresh grid."""
    session = "us4-rerank-001"
    _state1, _config = _run_graph(session)
    _events, state, _config = await _collect_stream(
        session, "I care more about comfort than sound quality"
    )
    assert state.get("error") is None
    assert state.get("followup") is None  # not a fast-path turn
    assert state["plan"]["root"]["type"] == "product_grid"
    # The mock weight handler reflects the NEW priorities (comfort outranks
    # nothing here; anc persisted from turn 1, sound is new).
    assert state["weights"] == {
        "anc": 1.0,
        "comfort": 0.7,
        "battery": 0.0,
        "sound": 0.5,
        "value": 0.0,
    }
    # D3: the model never orders — the ranking is exactly the pure scorer's.
    expected = score_products(state["candidates"], state["weights"])
    assert [s.product_id for s in state["ranked"]] == [s.product_id for s in expected]
    assert state["selected_ids"] == [s.product_id for s in expected[:3]]


async def test_us4_followup_turn_makes_exactly_one_llm_call(fake_llm_factory) -> None:
    """Follow-up turns skip the intent and narration LLM calls (deterministic
    resolution and assembly, plan included); only the weights call touches a
    model."""
    session = "us4-onecall-001"
    _state1, _config = _run_graph(session)
    fake = fake_llm_factory([])  # unscripted calls fall back to default handlers
    _events, state, _config = await _collect_stream(session, "compare the first two")
    assert state.get("error") is None
    assert state["plan"]["root"]["type"] == "comparison_table"
    assert fake.calls == [("PreferenceWeights", None)]


# ---------------------------------------------------------------------------
# US5: fault injection, determinism, fail-clean
# ---------------------------------------------------------------------------


async def test_us5_double_validation_failure_yields_single_clean_error(
    fake_llm_factory,
) -> None:
    """Acceptance 3: invalid model output twice -> exactly one retry, then a
    clean typed failure; no prose, no plan, nothing after the raise."""
    marker = "way-too-loud"
    fake = fake_llm_factory(
        [
            {"schema": "PreferenceWeights", "invalid": {"anc": marker}},
            {"schema": "PreferenceWeights", "invalid": {"anc": marker}},
        ]
    )
    graph: CompiledStateGraph = get_graph()
    session_id = "us5-fault-001"
    config = {"configurable": {"thread_id": session_id}}
    events: list[tuple[str, dict]] = []
    with pytest.raises(StructuredOutputError):
        async for payload in graph.astream(
            {
                "pending_user_text": FLIGHTS_MESSAGE,
                "pending_ui_action": None,
                "session_id": session_id,
            },
            config=config,
            stream_mode="custom",
        ):
            kind, data = payload
            events.append((kind, data))

    statuses = [data["stage"] for kind, data in events if kind == "status"]
    assert statuses == list(STAGE_ORDER)[:-1]  # stops at "ranking"
    assert [kind for kind, _data in events if kind == "message_delta"] == []
    assert [kind for kind, _data in events if kind == "ui_update"] == []
    # Exactly one retry: two invocations of the scripted schema, the rest on
    # default handlers.
    assert [call for call in fake.calls if call[0] == "PreferenceWeights"] == [
        ("PreferenceWeights", 0),
        ("PreferenceWeights", 1),
    ]
    # SC-007: no raw model output leaks into any streamed frame.
    assert marker not in repr(events)


async def test_us5_single_validation_failure_recovers_on_retry(fake_llm_factory) -> None:
    """One invalid output -> retry with the error fed back -> turn completes."""
    fake = fake_llm_factory(
        [
            {"invalid": {"budget_usd": "lots"}},
            {
                "valid": {
                    "category": "headphones",
                    "budget_usd": 180,
                    "priorities": {"anc": 1.0},
                }
            },
        ]
    )
    events, state, _config = await _collect_stream("us5-retry-001", FLIGHTS_MESSAGE)
    assert state.get("error") is None
    assert state["plan"]["root"]["type"] == "product_grid"
    assert [kind for kind, _data in events if kind == "message_delta"]
    # IntentExtraction consumed the scripted pair (invalid + valid retry);
    # every later call fell back to the default mock handlers. Plan assembly
    # makes no model call (code-owned since the review fix).
    assert fake.calls == [
        ("IntentExtraction", 0),
        ("IntentExtraction", 1),
        ("PreferenceWeights", None),
        ("Narration", None),
    ]


async def test_us5_identical_ranking_and_text_across_sessions_and_runs() -> None:
    """SC-002: two fresh sessions x 3 runs -> identical rankings AND identical
    streamed answer text, item-for-item and byte-for-byte."""

    async def signature(session_id: str) -> tuple[list[tuple[str, float]], str]:
        events, state, _config = await _collect_stream(session_id, FLIGHTS_MESSAGE)
        ranking = [(scored.product_id, scored.score) for scored in state["ranked"]]
        text = "".join(data["text"] for kind, data in events if kind == "message_delta")
        return ranking, text

    runs_a = [await signature(f"us5-det-a{run}") for run in range(1, 4)]
    runs_b = [await signature(f"us5-det-b{run}") for run in range(1, 4)]
    assert len({repr(signature_value) for signature_value in runs_a + runs_b}) == 1
    assert runs_a[0][0][0][0] == EXPECTED_TOP3[0]


# ---------------------------------------------------------------------------
# US5b: the native -> JSON-mode downgrade trigger is narrowed (review fix):
# ONLY provider request-contract rejections (status 400/404/422) permanently
# downgrade a model; transient failures re-raise untouched.
# ---------------------------------------------------------------------------


class _ProviderError(Exception):
    """Provider-style request error carrying an HTTP ``status_code``."""

    def __init__(self, status_code: int | None) -> None:
        super().__init__(f"provider error (status={status_code})")
        self.status_code = status_code


class _NativeRejectingLLM:
    """Fake LLM whose native structured call raises; JSON fallback works.

    Same consumer surface ``call_structured`` uses: ``with_structured_output``
    returns a runnable whose ``invoke`` raises *error*; plain ``invoke``
    (the JSON-mode path) returns a valid PreferenceWeights document.
    """

    def __init__(self, model_name: str, error: Exception) -> None:
        self.model_name = model_name
        self._error = error
        self.json_invocations = 0

    def with_structured_output(self, _schema: type) -> object:
        outer = self

        class _Bound:
            def invoke(self, _messages: object) -> object:
                raise outer._error

        return _Bound()

    def invoke(self, _messages: object) -> str:
        self.json_invocations += 1
        return '{"anc": 1.0, "comfort": 0.8, "battery": 0.0, "sound": 0.0, "value": 0.0}'


def test_native_contract_rejection_400_downgrades_to_json_mode() -> None:
    """status_code=400 -> permanent JSON-mode downgrade, turn still succeeds."""
    llm = _NativeRejectingLLM("fake-contract-reject-400", _ProviderError(400))
    result = call_structured(llm, PreferenceWeights, "weights please")
    assert result.anc == 1.0
    assert llm.json_invocations == 1
    assert "fake-contract-reject-400" in _JSON_MODE_MODELS


def test_native_contract_rejection_404_and_422_downgrade_too() -> None:
    """404/422 are the other in-contract rejections (unknown route / schema)."""
    for status in (404, 422):
        model_name = f"fake-contract-reject-{status}"
        llm = _NativeRejectingLLM(model_name, _ProviderError(status))
        result = call_structured(llm, PreferenceWeights, "weights please")
        assert result.comfort == 0.8
        assert model_name in _JSON_MODE_MODELS


def test_transient_native_failure_reraises_without_downgrade() -> None:
    """5xx -> original exception re-raised, model NOT downgraded to JSON."""
    llm = _NativeRejectingLLM("fake-transient-503", _ProviderError(503))
    with pytest.raises(_ProviderError):
        call_structured(llm, PreferenceWeights, "weights please")
    assert llm.json_invocations == 0
    assert "fake-transient-503" not in _JSON_MODE_MODELS


def test_exception_without_status_code_reraises_without_downgrade() -> None:
    """Plain timeouts/connection errors carry no status_code: re-raise."""
    llm = _NativeRejectingLLM("fake-timeout", TimeoutError("read timed out"))
    with pytest.raises(TimeoutError):
        call_structured(llm, PreferenceWeights, "weights please")
    assert llm.json_invocations == 0
    assert "fake-timeout" not in _JSON_MODE_MODELS
