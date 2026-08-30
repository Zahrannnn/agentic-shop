"""US4 follow-up resolver unit tests (pure module ``app.graph.followups``).

The resolver was extracted from ``app.graph.nodes`` (architecture-review
fix); these tests moved with it verbatim from ``test_graph_happy_path.py``
(imports adjusted to the new home only — zero behavior change). Graph-level
follow-up scenarios (full pipeline over real state) remain in
``test_graph_happy_path.py``.
"""

from __future__ import annotations

import pytest

from app.graph.followups import NO_PRODUCTS_DISCLOSURE, FollowUp, resolve_followup

pytestmark = pytest.mark.usefixtures("mock_settings")

FLIGHTS_MESSAGE: str = (
    "Help me find the best headphones for long flights under $200. "
    "Noise cancellation and comfort matter most."
)

#: Deterministic mock-mode podium for the flights request (same expectation
#: as the graph-level suite).
EXPECTED_TOP3: list[str] = ["aurora-hush-pro", "cloudline-air", "maple-ridge-comfort-150"]


def _followup_state(
    text: str,
    selected: list[str] | None = None,
    ranked: list[str] | None = None,
    action: dict | None = None,
) -> dict:
    """Synthetic session state for the pure follow-up resolver.

    ``selected`` defaults to the presented podium (as after a grid turn);
    pass ``selected=[]`` for an empty session.
    """
    return {
        "pending_user_text": text,
        "pending_ui_action": action,
        "selected_ids": list(EXPECTED_TOP3 if selected is None else selected),
        # ranked entries as plain dicts — exercises the restore-tolerant
        # branch of the resolver's ranking reader.
        "ranked": [{"product_id": pid} for pid in (ranked or [])],
    }


def test_us4_resolve_followup_patterns() -> None:
    """Table-driven coverage of the deterministic text/action fast paths."""
    first, second, third = EXPECTED_TOP3
    assert resolve_followup(_followup_state("compare the first two")) == FollowUp(
        "compare", (first, second)
    )
    assert resolve_followup(_followup_state("Compare 1 and 2 please")) == FollowUp(
        "compare", (first, second)
    )
    assert resolve_followup(_followup_state("compare the second and the third")) == FollowUp(
        "compare", (second, third)
    )
    assert resolve_followup(_followup_state("tell me more about the second one")) == FollowUp(
        "details", (second,)
    )
    # A bare positional reference inspects that product (US4 details turn).
    assert resolve_followup(_followup_state("the second one")) == FollowUp("details", (second,))
    # "that one" resolves to the LAST selected id (prescribed semantics),
    # falling back to ranked[0] when nothing was selected.
    assert resolve_followup(_followup_state("THAT ONE")) == FollowUp("details", (third,))
    assert resolve_followup(
        _followup_state("that one", selected=[], ranked=[first, second, third])
    ) == FollowUp("details", (first,))
    assert resolve_followup(_followup_state("add the first one to my cart")) == FollowUp(
        "add_to_cart", (first,)
    )
    assert resolve_followup(_followup_state("add that one to my cart")) == FollowUp(
        "add_to_cart", (third,)
    )
    assert resolve_followup(_followup_state("remove the first one from my cart")) == FollowUp(
        "remove_from_cart", (first,)
    )
    assert resolve_followup(_followup_state("what's in my cart?")) == FollowUp("cart_view")
    assert resolve_followup(_followup_state("show my cart")) == FollowUp("cart_view")

    # ui_action path: payload ids win; the grid's payload-less compare falls
    # back to the presented top two; unknown payload ids fall back to the
    # last selected product.
    assert resolve_followup(
        _followup_state(
            "", action={"type": "choose", "label": "x", "payload": {"productId": second}}
        )
    ) == FollowUp("details", (second,))
    # The grid's bare Compare button compares EVERY presented pick (up to
    # three); explicit positions keep their exact selection.
    assert resolve_followup(
        _followup_state("", action={"type": "compare", "label": "Compare", "payload": {}})
    ) == FollowUp("compare", (first, second, third))
    assert resolve_followup(
        _followup_state(
            "", action={"type": "details", "label": "Details", "payload": {"productId": "nope"}}
        )
    ) == FollowUp("details", (third,))

    # Unresolvable targets: a clean disclosure, never an error.
    assert resolve_followup(
        {"pending_user_text": "compare the first two", "pending_ui_action": None}
    ) == FollowUp("disclosure", (), NO_PRODUCTS_DISCLOSURE)

    # Normal pipeline: full requests and chatter never fast-path; bare
    # positional references on an empty session are just prose.
    assert resolve_followup(_followup_state(FLIGHTS_MESSAGE)) is None
    assert resolve_followup(_followup_state("hello there")) is None
    assert resolve_followup(_followup_state("")) is None
    assert (
        resolve_followup(
            {"pending_user_text": "my first pair of headphones", "pending_ui_action": None}
        )
        is None
    )
