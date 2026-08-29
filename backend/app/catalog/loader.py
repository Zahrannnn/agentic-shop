"""Catalog loading and normalization helpers.

`load_catalog` is the only sanctioned way to read the curated dataset: it
validates every record through the Pydantic `Product` model and fails loudly
on malformed data or duplicate ids (D5, R10).

The normalization helpers (`min_max`, `anc_ordinal`) implement the math the
pure scorer relies on (research.md R6); they are side-effect free so ranking
stays a pure function (D3).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.catalog.models import ANCType, Product

#: Default dataset packaged with the app (one file per category in the MVP).
DEFAULT_DATA_PATH: Path = Path(__file__).parent / "data" / "headphones.json"

#: Ordinal scale for `ANCType`, per research.md R6 (none 0 -> adaptive 1).
_ANC_ORDINALS: dict[ANCType, float] = {
    ANCType.NONE: 0.0,
    ANCType.PASSIVE: 0.33,
    ANCType.ACTIVE: 0.66,
    ANCType.ADAPTIVE: 1.0,
}


def load_catalog(path: Path | None = None) -> list[Product]:
    """Load and validate the product catalog.

    Every record is validated through the `Product` model; the first malformed
    record or duplicate id raises `ValueError` with its index/id for context.

    Args:
        path: Optional path to a catalog JSON file. Defaults to the packaged
            ``data/headphones.json`` next to this module.

    Returns:
        All products, sorted by id so downstream consumers see a deterministic
        order regardless of how the JSON file is arranged.

    Raises:
        ValueError: If the file cannot be read or parsed, is not a JSON array,
            contains a record that fails `Product` validation, or contains
            duplicate product ids.
    """
    file = path if path is not None else DEFAULT_DATA_PATH
    try:
        raw_text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"catalog file '{file}' could not be read: {exc}") from exc

    try:
        raw_records = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"catalog file '{file}' is not valid JSON: {exc}") from exc

    if not isinstance(raw_records, list):
        raise ValueError(f"catalog file '{file}' must contain a JSON array of products")

    products: list[Product] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(raw_records):
        try:
            product = Product.model_validate(record)
        except ValueError as exc:  # pydantic ValidationError subclasses ValueError
            raise ValueError(f"malformed catalog record at index {index}: {exc}") from exc
        if product.id in seen_ids:
            raise ValueError(f"duplicate product id '{product.id}' in catalog file '{file}'")
        seen_ids.add(product.id)
        products.append(product)

    return sorted(products, key=lambda product: product.id)


def min_max(values: list[float], invert: bool = False) -> list[float]:
    """Min-max normalize ``values`` into [0, 1] across the given set (R6).

    With ``invert=False`` the smallest input maps to 0.0 and the largest to
    1.0 ("higher is better"). With ``invert=True`` the scale is flipped so the
    smallest input maps to 1.0 and the largest to 0.0 — use this for cost
    attributes such as price or weight ("cheaper/lighter is better").

    If every value is identical (or the list is empty and a constant is
    needed), all positions score the neutral ``0.5`` so a degenerate attribute
    contributes nothing directional to the ranking.

    Args:
        values: Raw attribute values, positionally aligned with the candidates.
        invert: When True, treat the attribute as a cost (1.0 = smallest value).

    Returns:
        Normalized values, positionally aligned with the input.
    """
    if not values:
        return []
    low, high = min(values), max(values)
    if low == high:
        return [0.5 for _ in values]
    span = high - low
    if invert:
        return [(high - value) / span for value in values]
    return [(value - low) / span for value in values]


def anc_ordinal(anc_type: ANCType | str) -> float:
    """Map an ``ANCType`` onto its scorer ordinal (research.md R6).

    Scale: none 0.0, passive 0.33, active 0.66, adaptive 1.0.

    Args:
        anc_type: An `ANCType` member or its string value.

    Returns:
        The ordinal in [0, 1].

    Raises:
        ValueError: If ``anc_type`` is not a valid ANCType value.
    """
    return _ANC_ORDINALS[ANCType(anc_type)]
