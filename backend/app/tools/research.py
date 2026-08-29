"""Pure research tools over the pre-scored catalog (Phase 1, DECISIONS.md D5).

Review data is curated and pre-scored at build time; these tools only READ
it. There is deliberately no NLP, embedding, or sentiment extraction over
quote text at runtime (D5 / FR-005): scores are surfaced verbatim and quotes
are displayed, never parsed.

Purity: every function here is side-effect free — no mutation of the catalog,
no I/O, no randomness. Identical inputs produce identical outputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.catalog.models import Product


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    """Pre-scored review payload for one product, read verbatim from the catalog.

    ``review_scores`` (attribute -> 0.0-5.0 score) and ``quotes`` are defensive
    copies detached from the catalog models, so mutating a summary can never
    leak into shared catalog state. NO runtime NLP is applied to ``quotes``
    (D5) — they are carried as-is for display.
    """

    product_id: str
    review_scores: dict[str, float]
    quotes: tuple[str, ...]


def get_product_specs(catalog: Sequence[Product], product_id: str) -> Product | None:
    """Return the full catalog record for ``product_id``, or ``None`` if unknown.

    Pure lookup: the validated :class:`Product` instance from ``catalog`` is
    returned as-is (not copied) — treat it as read-only.

    Args:
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_id: Stable slug, e.g. ``"aurora-hush-pro"``.

    Returns:
        The matching product, or ``None`` when the id is not in the catalog.
    """
    for product in catalog:
        if product.id == product_id:
            return product
    return None


def get_product_reviews(catalog: Sequence[Product], product_id: str) -> ReviewSummary | None:
    """Return the pre-scored review summary for ``product_id``, or ``None``.

    Values come straight from the catalog's pre-scored data (D5): scores are
    copied into a plain dict, quotes into a tuple. No runtime NLP over quotes.

    Args:
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_id: Stable slug, e.g. ``"aurora-hush-pro"``.

    Returns:
        A :class:`ReviewSummary`, or ``None`` when the id is not in the catalog.
    """
    product = get_product_specs(catalog, product_id)
    if product is None:
        return None
    return ReviewSummary(
        product_id=product.id,
        review_scores=dict(product.review_scores.model_dump()),
        quotes=tuple(product.quotes),
    )


def summarize_candidates(
    catalog: Sequence[Product],
    product_ids: Sequence[str],
) -> list[ReviewSummary]:
    """Summarize reviews for ``product_ids``, preserving input order.

    Unknown ids are skipped silently — the graph validates ids against the
    catalog upstream (e.g. when dropping invalid narrated ids), so this stays
    a total, pure function. Duplicate ids yield one summary per occurrence.

    Args:
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_ids: Candidate ids in presentation order.

    Returns:
        One :class:`ReviewSummary` per known id, in input order.
    """
    summaries: list[ReviewSummary] = []
    for product_id in product_ids:
        summary = get_product_reviews(catalog, product_id)
        if summary is not None:
            summaries.append(summary)
    return summaries
