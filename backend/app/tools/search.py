"""Pure product-search tools (Phase 1).

``search_products`` filters the catalog against a :class:`SearchFilters`
value; ``relax_filters`` derives progressively looser variants for the
"empty results -> closest matches, disclose what was relaxed" edge case
(DECISIONS.md D4: contradictory constraints -> proceed honestly). The graph
owns the *policy* of when to relax; these helpers only supply the mechanics.

Purity: both functions are side-effect free. They never mutate the catalog or
the filters, do no I/O, and use no randomness or wall clock — identical inputs
always produce identical outputs in identical order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.catalog.models import ANCType, Product

#: Dollars by which ``max_price`` is raised per price-relaxation step.
PRICE_RELAX_STEP_USD: float = 50.0

#: How many ``+$50`` price-raising steps run before the cap is removed outright.
PRICE_RELAX_STEPS: int = 2


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Structured hard filters for :func:`search_products`.

    Every field is an optional constraint; the default value means "do not
    constrain" and is skipped during matching.

    Semantics:

    * ``category`` — exact match, case-insensitive (the input is stripped).
    * ``max_price`` — **inclusive** upper bound: ``price_usd <= max_price``.
    * ``min_battery_hours`` — **inclusive** lower bound:
      ``battery_hours >= min_battery_hours``.
    * ``require_anc`` — when ``True``, keeps products with any noise control,
      i.e. ``anc_type != "none"``; ``passive`` counts as ANC because it
      isolates physically. The default ``False`` imposes no ANC constraint
      (it does *not* mean "must not have ANC").
    * ``codecs`` — AND semantics: a product matches only if it supports every
      requested codec (matched case-insensitively). An empty tuple constrains
      nothing.
    * ``multipoint`` / ``folding`` — when not ``None``, the product flag must
      equal the requested value.
    """

    category: str | None = None
    max_price: float | None = None
    min_battery_hours: float | None = None
    require_anc: bool = False
    codecs: tuple[str, ...] = ()
    multipoint: bool | None = None
    folding: bool | None = None


def _matches(product: Product, filters: SearchFilters) -> bool:
    """Return ``True`` when ``product`` satisfies every set constraint in ``filters``."""
    if (
        filters.category is not None
        and product.category.lower() != filters.category.strip().lower()
    ):
        return False
    if filters.max_price is not None and product.price_usd > filters.max_price:
        return False
    if filters.min_battery_hours is not None and product.battery_hours < filters.min_battery_hours:
        return False
    if filters.require_anc and product.anc_type == ANCType.NONE:
        return False
    if filters.codecs:
        wanted = {codec.lower() for codec in filters.codecs}
        if not wanted.issubset(product.codecs):
            return False
    if filters.multipoint is not None and product.multipoint != filters.multipoint:
        return False
    return not (filters.folding is not None and product.folding != filters.folding)


def search_products(catalog: Sequence[Product], filters: SearchFilters) -> list[Product]:
    """Return every catalog product matching ``filters``, in catalog order.

    Pure filter — no ranking, no relaxation, no mutation of ``catalog`` or
    ``filters``; identical inputs yield identical outputs. Results preserve
    the order of ``catalog`` (the loader already sorts by id, so the output
    is deterministic). An empty match set is a valid result: this function
    deliberately contains no relaxation logic — the graph handles the empty
    case, e.g. via :func:`relax_filters`.

    Args:
        catalog: Validated products, as produced by ``app.catalog.loader``.
        filters: Hard filters; unset fields are skipped.

    Returns:
        Matching products in catalog order; ``[]`` when nothing matches.
    """
    return [product for product in catalog if _matches(product, filters)]


def relax_filters(filters: SearchFilters) -> list[SearchFilters]:
    """Return progressively relaxed variants of ``filters`` (pure, deterministic).

    Used by the graph for the "no results -> closest matches (and disclose
    what was relaxed)" edge case: the caller searches with the original
    filter first, then walks the returned list in order until it finds
    matches. Each entry is strictly more permissive than the previous one.

    Progression:

    1. Drop attribute constraints one at a time, in this fixed order:
       ``codecs`` -> ``require_anc`` -> ``min_battery_hours`` ->
       ``multipoint`` -> ``folding``. Constraints that are already unset are
       skipped, so no no-op or duplicate steps appear.
    2. Then relax the price: raise ``max_price`` from its original value in
       ``+$50`` steps, up to two steps, and finally remove the cap entirely
       (``max_price=None``) as the last resort.

    Purity: ``filters`` is never mutated and never included in the result
    (the caller has, by definition, already searched with it). A filter with
    nothing left to relax yields ``[]``.
    """
    relaxed: list[SearchFilters] = []
    current = filters

    # 1. Attribute constraints, weakest-first, one drop per step.
    if filters.codecs:
        current = replace(current, codecs=())
        relaxed.append(current)
    if filters.require_anc:
        current = replace(current, require_anc=False)
        relaxed.append(current)
    if filters.min_battery_hours is not None:
        current = replace(current, min_battery_hours=None)
        relaxed.append(current)
    if filters.multipoint is not None:
        current = replace(current, multipoint=None)
        relaxed.append(current)
    if filters.folding is not None:
        current = replace(current, folding=None)
        relaxed.append(current)

    # 2. Price: +$50 steps from the original cap, then remove it entirely.
    if filters.max_price is not None:
        for step in range(1, PRICE_RELAX_STEPS + 1):
            relaxed.append(
                replace(current, max_price=filters.max_price + step * PRICE_RELAX_STEP_USD)
            )
        relaxed.append(replace(current, max_price=None))

    return relaxed
