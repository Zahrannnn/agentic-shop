"""US4 deterministic follow-up resolution — pure module, zero model calls.

Extracted verbatim from ``app.graph.nodes`` (architecture-review fix): the
resolver, its regex tables, and the :class:`FollowUp` value live here so the
graph nodes stay readable and the resolver can be unit-tested in isolation
(``tests/test_followups.py``). Pure in the graph sense: it reads only the
session-state dict passed in plus static catalog ids — no I/O of its own, no
clock, no randomness.

US4 follow-up turns (``resolve_followup``) are resolved deterministically in
the intent node BEFORE any model call, mirroring the chip fast-path: positional
and demonstrative references ("compare the first two", "add that one to my
cart") resolve against the session's presented products, and the matched turn
skips the intent and narration LLM calls (weights still flow through the
normal pipeline so ``ranked`` stays fresh).

``app.graph.nodes`` re-exports the public names (:class:`FollowUp`,
:func:`resolve_followup`, the shared constants) so existing import surfaces
keep working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.graph.state import ShoppingState

__all__ = [
    "COMPARISON_ATTRIBUTES",
    "FOLLOWUP_ACTION_TYPES",
    "FOLLOWUP_KINDS",
    "FollowUp",
    "MAX_COMPARE",
    "NO_PRODUCTS_DISCLOSURE",
    "TOP_N",
    "ranked_ids",
    "resolve_followup",
]

#: How many ranked products the plan presents and the narration covers. Also
#: the presented-list fallback size in the resolver (top-N of the checkpointed
#: ranking when no plan has been shown yet). Shared with ``app.graph.nodes``.
TOP_N: int = 3

#: UI-action types a follow-up turn resolves without any model call. A
#: ``choose`` action (the comparison table's pick button) maps to a details
#: turn: the shopper singled one product out, and the natural next step is
#: inspecting it.
FOLLOWUP_ACTION_TYPES: frozenset[str] = frozenset(
    {"compare", "details", "add_to_cart", "remove_from_cart", "choose"}
)

#: Attributes of every follow-up ``comparison_table`` (contracts/ui-dsl.md
#: and the ``comparison-two.json`` fixture agree on this list).
COMPARISON_ATTRIBUTES: tuple[str, ...] = (
    "price_usd",
    "battery_hours",
    "weight_g",
    "anc_type",
    "comfort",
)

#: Disclosure when a follow-up references products that were never presented
#: (invalid/missing targets end the turn cleanly — no error frame, US4).
NO_PRODUCTS_DISCLOSURE: str = "We haven't picked products yet — ask for a recommendation first."

#: Maximum targets of one comparison (DSL bound: 2-3 productIds).
MAX_COMPARE: int = 3

#: Follow-up turn kinds, as stored in ``state["followup"]["kind"]``.
FOLLOWUP_KINDS = (
    "compare",
    "details",
    "add_to_cart",
    "remove_from_cart",
    "cart_view",
    "disclosure",
)


@dataclass(frozen=True)
class FollowUp:
    """One deterministically resolved follow-up turn (US4).

    ``kind`` is one of :data:`FOLLOWUP_KINDS`; ``product_ids`` carries the
    resolved targets (empty for ``cart_view``/``disclosure``); ``disclosure``
    is set only for the ``disclosure`` kind, whose turn ends cleanly with a
    text_block plan instead of an error frame.
    """

    kind: str
    product_ids: tuple[str, ...] = ()
    disclosure: str | None = None

    def to_state(self) -> dict[str, Any]:
        """Plain-dict form stored under ``state["followup"]``."""
        return {
            "kind": self.kind,
            "product_ids": list(self.product_ids),
            "disclosure": self.disclosure,
        }


_CART_VIEW_RE = re.compile(
    r"\bwhat(?:['’]s| is)\s+in\s+(?:my |the )cart\b"
    r"|\b(?:show|view|open|see)\s+(?:my |the )cart\b",
    re.IGNORECASE,
)
_REMOVE_FROM_CART_RE = re.compile(r"\bremove\b[\s\S]*\bfrom\s+(?:my |the )?cart\b", re.IGNORECASE)
_ADD_TO_CART_RE = re.compile(r"\badd\b[\s\S]*\bto\s+(?:my |the )?cart\b", re.IGNORECASE)
_COMPARE_RE = re.compile(r"\bcompare\b", re.IGNORECASE)
# Only the explicit inspect phrases — a bare "more about" would false-match
# preference sentences like "I care more about comfort than sound quality".
_DETAILS_RE = re.compile(r"\btell me more about\b|\bdetails\b", re.IGNORECASE)
_DEMONSTRATIVE_RE = re.compile(r"\b(?:that|this)\s+one\b", re.IGNORECASE)

#: Ordinal words / bare digits -> 0-based position in the presented list.
#: Multi-position phrases -> ordered 0-based positions ("compare the
#: first two", "top three"). Checked before single ordinals.
#: Multi-position phrases -> ordered 0-based positions ("compare the
#: first two", "top three"). Checked before single ordinals.
_POSITION_PAIR_PATTERNS: tuple[tuple[re.Pattern[str], tuple[int, ...]], ...] = (
    (re.compile(r"\b(?:first|top)\s+three\b|\ball\s+three\b", re.IGNORECASE), (0, 1, 2)),
    (re.compile(r"\b(?:first|top)\s+two\b|\ball\s+two\b", re.IGNORECASE), (0, 1)),
)

_POSITION_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bfirst\b", re.IGNORECASE), 0),
    (re.compile(r"\bsecond\b", re.IGNORECASE), 1),
    (re.compile(r"\bthird\b", re.IGNORECASE), 2),
    (re.compile(r"\b1\b"), 0),
    (re.compile(r"\b2\b"), 1),
    (re.compile(r"\b3\b"), 2),
)


def ranked_ids(state: ShoppingState) -> list[str]:
    """Checkpointed ranking as plain ids (tolerates dicts after a restore)."""
    ids: list[str] = []
    for scored in state.get("ranked") or []:
        product_id = (
            scored.get("product_id")
            if isinstance(scored, dict)
            else getattr(scored, "product_id", None)
        )
        if isinstance(product_id, str):
            ids.append(product_id)
    return ids


def _presented_ids(state: ShoppingState) -> list[str]:
    """The products the client is currently showing (the last plan's ids).

    Positional references ("the first two") mean the presented order, i.e.
    ``selected_ids`` as stamped by the last grid/plan turn — falling back to
    the checkpointed ranking's top :data:`TOP_N` when no plan has been
    presented yet.
    """
    selected = [pid for pid in (state.get("selected_ids") or []) if isinstance(pid, str)]
    if selected:
        return selected
    return ranked_ids(state)[:TOP_N]


def _last_selected_id(state: ShoppingState) -> str | None:
    """Target of "that one"/"this one": the last selected id, else ranked[0]."""
    selected = [pid for pid in (state.get("selected_ids") or []) if isinstance(pid, str)]
    if selected:
        return selected[-1]
    ranked = ranked_ids(state)
    return ranked[0] if ranked else None


def _mentioned_positions(text: str) -> list[int]:
    """0-based positions of ordinal/digit references, in order of appearance."""
    lowered = text.lower()
    for pattern, pair in _POSITION_PAIR_PATTERNS:
        if pattern.search(lowered):
            return list(pair)
    positions: list[int] = []
    for pattern, position in _POSITION_PATTERNS:
        if position not in positions and pattern.search(lowered):
            positions.append(position)
    return positions


def _text_target_id(text: str, state: ShoppingState) -> str | None:
    """Resolve the product a cart/details phrase points at.

    Precedence: an explicit ordinal ("the second one") in the presented list,
    then a demonstrative ("that one" -> last selected), then the top pick.
    """
    presented = _presented_ids(state)
    for position in _mentioned_positions(text):
        if position < len(presented):
            return presented[position]
    if _DEMONSTRATIVE_RE.search(text):
        return _last_selected_id(state)
    return presented[0] if presented else None


def _no_products() -> FollowUp:
    """The standard clean disclosure for unresolvable targets."""
    return FollowUp(kind="disclosure", disclosure=NO_PRODUCTS_DISCLOSURE)


def catalog_id_set() -> set[str]:
    """Valid catalog ids as a set (pure read of the process-wide catalog).

    The import is deferred on purpose: ``app.graph.nodes`` owns the catalog
    singleton (:func:`app.graph.nodes.get_catalog`) and imports THIS module at
    its module level, so a top-level import here would be circular. Resolver
    calls happen at turn time, when both modules are fully loaded.
    """
    from app.graph.nodes import get_catalog  # noqa: PLC0415 — cycle breaker

    return {product.id for product in get_catalog()}


def _resolve_action_followup(action: dict[str, Any], state: ShoppingState) -> FollowUp | None:
    """Resolve a follow-up against the echoed ``ui_action`` (US4 contract:
    targets come from ``payload["productId"]``/``payload["productIds"]``,
    falling back to the presented list; unknown payload ids are ignored in
    favor of the positional default)."""
    kind = action.get("type")
    if kind not in FOLLOWUP_ACTION_TYPES:
        return None
    payload = action.get("payload") or {}
    presented = _presented_ids(state)
    catalog_ids = catalog_id_set()
    if kind == "compare":
        raw_ids = payload.get("productIds")
        if isinstance(raw_ids, (list, tuple)):
            valid = [pid for pid in raw_ids if isinstance(pid, str) and pid in catalog_ids][
                :MAX_COMPARE
            ]
            if len(valid) >= 2:
                return FollowUp(kind="compare", product_ids=tuple(valid))
        if len(presented) >= 2:
            # Bare grid-level Compare: every presented pick, up to the table cap.
            return FollowUp(kind="compare", product_ids=tuple(presented[:MAX_COMPARE]))
        return _no_products()
    target = payload.get("productId")
    if not isinstance(target, str) or target not in catalog_ids:
        target = _last_selected_id(state)
    if target is None:
        return _no_products()
    if kind in ("details", "choose"):
        return FollowUp(kind="details", product_ids=(target,))
    if kind == "add_to_cart":
        return FollowUp(kind="add_to_cart", product_ids=(target,))
    return FollowUp(kind="remove_from_cart", product_ids=(target,))


def _resolve_text_followup(text: str, state: ShoppingState) -> FollowUp | None:
    """Resolve a follow-up from the message text (deterministic regexes).

    Checked in this fixed order: cart view, remove, add, compare, details,
    then bare positional/demonstrative references (which only count as a
    follow-up once products have actually been presented — a first message
    like "my first pair of headphones" must stay a normal request). ``None``
    means no pattern matched: the normal LLM pipeline runs.
    """
    presented = _presented_ids(state)
    if _CART_VIEW_RE.search(text):
        return FollowUp(kind="cart_view")
    if _REMOVE_FROM_CART_RE.search(text):
        target = _text_target_id(text, state)
        if target is None:
            return _no_products()
        return FollowUp(kind="remove_from_cart", product_ids=(target,))
    if _ADD_TO_CART_RE.search(text):
        target = _text_target_id(text, state)
        if target is None:
            return _no_products()
        return FollowUp(kind="add_to_cart", product_ids=(target,))
    if _COMPARE_RE.search(text):
        positions = [p for p in _mentioned_positions(text) if p < len(presented)]
        if len(positions) >= 2:
            targets = tuple(presented[p] for p in positions[:MAX_COMPARE])
            return FollowUp(kind="compare", product_ids=targets)
        if len(presented) >= 2:
            # No explicit positions: compare every presented pick (up to the
            # table cap) — "compare the first two" with explicit positions is
            # handled by the positional branch above.
            return FollowUp(kind="compare", product_ids=tuple(presented[:MAX_COMPARE]))
        return _no_products()
    if _DETAILS_RE.search(text):
        target = _text_target_id(text, state)
        if target is None:
            return _no_products()
        return FollowUp(kind="details", product_ids=(target,))
    if not presented:
        return None
    if _DEMONSTRATIVE_RE.search(text):
        target = _last_selected_id(state)
        if target is not None:
            return FollowUp(kind="details", product_ids=(target,))
        return None
    for pattern, position in _POSITION_PATTERNS[:3]:  # ordinal words only
        if pattern.search(text) and position < len(presented):
            # A bare positional reference ("the second one") inspects that
            # product — the details turn of US4.
            return FollowUp(kind="details", product_ids=(presented[position],))
    return None


def resolve_followup(state: ShoppingState) -> FollowUp | None:
    """Pure US4 entry point: resolve a follow-up turn from session state.

    Returns ``None`` when nothing matches (normal pipeline). The ui_action
    path wins over the text path when both are present; ``select_preference``
    chip actions are never follow-ups (the chip fast-path owns those).
    """
    action = state.get("pending_ui_action")
    if isinstance(action, dict):
        resolved = _resolve_action_followup(action, state)
        if resolved is not None:
            return resolved
    text = str(state.get("pending_user_text") or "").strip()
    if text:
        return _resolve_text_followup(text, state)
    return None
