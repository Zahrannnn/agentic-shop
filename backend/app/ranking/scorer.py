"""Pure deterministic product scorer (DECISIONS.md D3, research.md R6).

Ranking is a pure Python function; the LLM only ever produces preference
*weights*, never an order. This module is the constitution's principle III
made code.

Determinism contract (FR-015 / SC-002)
--------------------------------------
* Pure: no I/O, no clock, no randomness, no mutable module state. Identical
  ``candidates`` and ``weights`` always produce byte-identical output
  (``repr``-stable), so the same input yields the same ranking every time.
* Attribute values are min-max normalized **across the current candidate
  set**, so results depend on set membership only, never on input order.
* Attributes are iterated in a canonical order, so the ``contributions``
  dict repr does not depend on the caller's mapping key order.
* Scores and contributions are rounded to 10 decimal places and the final
  sort uses the rounded score, so last-bit floating-point noise cannot
  change the ordering.
* The sort is total: score descending, ties broken by ``product_id``
  ascending (lexicographic). Ranks are ``1..n`` in output order.

Attributes
----------
The five scorable review attributes (:data:`SCORABLE_ATTRIBUTES`) always
apply; weights for them are expected from the LLM (research.md R6 step 1):

* ``battery`` -> min-max of ``battery_hours`` (higher is better)
* ``comfort`` -> min-max of ``review_scores.comfort / 5.0`` (higher is better)
* ``anc``     -> min-max of ``review_scores.anc / 5.0`` (higher is better)
* ``sound``   -> min-max of ``review_scores.sound / 5.0`` (higher is better)
* ``value``   -> min-max of ``review_scores.value / 5.0`` (higher is better)

Three optional attributes (:data:`OPTIONAL_ATTRIBUTES`) are scored only when
the weights mapping contains them:

* ``anc_type`` -> min-max of the ``anc_ordinal`` scale (none 0 -> passive
  0.33 -> active 0.66 -> adaptive 1, then rescaled across the candidate set)
* ``price``  -> min-max of ``price_usd`` inverted (cheaper is better)
* ``weight`` -> min-max of ``weight_g`` inverted (lighter is better)

Weight handling: weights over known attributes are normalized to sum to 1;
unknown keys are ignored; negative or non-finite values are treated as 0.
If no positive weight remains, the five scorable attributes fall back to a
uniform ``0.2`` each. Missing attribute values (defensive only -- the
``Product`` model makes them required) score a neutral ``0.5``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from app.catalog.loader import anc_ordinal, min_max
from app.catalog.models import Product

#: The five always-scorable attributes (research.md R6 step 1).
SCORABLE_ATTRIBUTES: tuple[str, ...] = ("battery", "comfort", "anc", "sound", "value")

#: Extra attributes scored only when present in the weights mapping.
OPTIONAL_ATTRIBUTES: tuple[str, ...] = ("anc_type", "price", "weight")

#: Every attribute the scorer understands; other weight keys are ignored.
KNOWN_ATTRIBUTES: tuple[str, ...] = SCORABLE_ATTRIBUTES + OPTIONAL_ATTRIBUTES

#: Cost attributes: min-max normalized with ``invert=True`` (lower is better).
_INVERTED_ATTRIBUTES: frozenset[str] = frozenset({"price", "weight"})

#: Attributes sourced from ``review_scores`` scaled to [0, 1] by dividing by 5.
_REVIEW_ATTRIBUTES: frozenset[str] = frozenset({"comfort", "anc", "sound", "value"})

#: Decimal places kept for byte-stable scores and contributions (FR-015).
_ROUND_DIGITS: int = 10

#: Neutral score used when an attribute value is missing or degenerate.
_NEUTRAL: float = 0.5


@dataclass(frozen=True)
class ScoredProduct:
    """One candidate with its deterministic score and per-attribute breakdown.

    ``contributions`` maps attribute name to its weighted contribution
    (``weight_attr * normalized_attr``, rounded); only attributes with a
    positive weight appear, so ``sum(contributions) == score`` up to the
    10-decimal rounding.
    """

    product_id: str
    score: float
    contributions: dict[str, float]
    rank: int


def _normalized_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Normalize weights over the known attributes so they sum to 1 (R6 step 2).

    Unknown keys are ignored; negative or non-finite values are treated as
    0. When no positive weight remains, the five scorable attributes fall
    back to a uniform ``1 / len(SCORABLE_ATTRIBUTES)`` each.
    """
    cleaned: dict[str, float] = {}
    for attr in KNOWN_ATTRIBUTES:
        try:
            raw = float(weights.get(attr, 0.0))
        except (TypeError, ValueError):
            raw = 0.0
        cleaned[attr] = raw if math.isfinite(raw) and raw > 0.0 else 0.0
    total = math.fsum(cleaned.values())
    if total <= 0.0:
        uniform = 1.0 / len(SCORABLE_ATTRIBUTES)
        return {
            attr: (uniform if attr in SCORABLE_ATTRIBUTES else 0.0) for attr in KNOWN_ATTRIBUTES
        }
    return {attr: value / total for attr, value in cleaned.items()}


def _raw_values(attr: str, candidates: Sequence[Product]) -> list[float | None]:
    """Extract raw values of ``attr`` aligned with ``candidates``.

    Returns ``None`` positions for values that cannot be extracted
    (defensive; the ``Product`` model makes every field required). Review
    attributes are pre-scaled to [0, 1] by dividing the 0-5 score by 5.0.
    """
    values: list[float | None] = []
    for product in candidates:
        value: float | None
        try:
            if attr == "battery":
                value = float(product.battery_hours)
            elif attr in _REVIEW_ATTRIBUTES:
                value = float(getattr(product.review_scores, attr)) / 5.0
            elif attr == "anc_type":
                value = anc_ordinal(product.anc_type)
            elif attr == "price":
                value = float(product.price_usd)
            elif attr == "weight":
                value = float(product.weight_g)
            else:  # pragma: no cover - callers only pass KNOWN_ATTRIBUTES
                value = None
        except (AttributeError, KeyError, TypeError, ValueError):
            value = None
        values.append(value)
    return values


def _normalized_values(attr: str, candidates: Sequence[Product]) -> list[float]:
    """Min-max normalize one attribute across the candidate set (R6 step 3).

    Cost attributes (``price``, ``weight``) are inverted so the smallest raw
    value scores 1.0. Positions with a missing value score the neutral
    ``0.5``; if no value is present at all, every position is neutral.
    """
    raw = _raw_values(attr, candidates)
    present = [value for value in raw if value is not None]
    if not present:
        return [_NEUTRAL for _ in raw]
    normalized_present = min_max(present, invert=attr in _INVERTED_ATTRIBUTES)
    filled: Iterator[float] = iter(normalized_present)
    return [next(filled) if value is not None else _NEUTRAL for value in raw]


def score_products(
    candidates: Sequence[Product], weights: Mapping[str, float]
) -> list[ScoredProduct]:
    """Score ``candidates`` against preference ``weights`` (research.md R6).

    Steps: normalize the weights to sum to 1 over the known attributes
    (unknown keys ignored; all-zero/missing -> uniform 0.2 over the five
    scorable attributes), min-max normalize every weighted attribute across
    the candidate set, sum ``weight * normalized`` per product, then sort by
    rounded score descending with ties broken by ``product_id`` ascending.
    Ranks are ``1..n`` in the returned order.

    Args:
        candidates: The candidate products, in any order (output is
            order-independent).
        weights: Preference weights per attribute; only known attributes
            (see :data:`KNOWN_ATTRIBUTES`) are considered. Optional
            attributes (``anc_type``, ``price``, ``weight``) participate
            only when present here.

    Returns:
        One :class:`ScoredProduct` per candidate, best first. An empty
        candidate list yields an empty list.
    """
    if not candidates:
        return []

    attr_weights = _normalized_weights(weights)
    normalized: dict[str, list[float]] = {
        attr: _normalized_values(attr, candidates)
        for attr in KNOWN_ATTRIBUTES
        if attr_weights[attr] > 0.0
    }

    drafts: list[tuple[float, str, dict[str, float]]] = []
    for index, product in enumerate(candidates):
        contributions: dict[str, float] = {}
        total = 0.0
        for attr in KNOWN_ATTRIBUTES:  # canonical order -> byte-stable repr
            weight = attr_weights[attr]
            if weight <= 0.0:
                continue
            contribution = weight * normalized[attr][index]
            total += contribution
            contributions[attr] = round(contribution, _ROUND_DIGITS)
        drafts.append((round(total, _ROUND_DIGITS), product.id, contributions))

    # Total order: rounded score desc, then product id asc (R6 step 5).
    drafts.sort(key=lambda draft: (-draft[0], draft[1]))
    return [
        ScoredProduct(product_id=product_id, score=score, contributions=contribs, rank=rank)
        for rank, (score, product_id, contribs) in enumerate(drafts, start=1)
    ]
