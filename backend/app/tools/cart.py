"""Pure mock-cart tools (Phase 1, feature 001).

The cart is per-session state (``ShoppingState.cart``): an ordered list of
:class:`CartItem` dicts, ``{"product_id": str, "quantity": int}``. These
helpers implement the add / remove / set / view mechanics; the graph owns the
*policy* of when to call them. Totals are computed from catalog prices only
(data-model.md, CartItem).

Purity: every function here is side-effect free and deterministic — the input
cart is never mutated (a modified copy is always returned, and every returned
line dict is freshly built), there is no I/O, no randomness, no wall clock.
Identical inputs always produce identical outputs, including error behavior.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

from app.catalog.models import Product

#: Hard per-line quantity cap (data-model.md: ``CartItem.quantity`` is 1-10).
MAX_QUANTITY: int = 10


class CartItem(TypedDict):
    """One cart line as stored in session state (a plain dict at runtime)."""

    product_id: str
    quantity: int


@dataclass(frozen=True, slots=True)
class CartLine:
    """A priced cart line produced by :func:`get_cart` (display, 2-decimal)."""

    product_id: str
    quantity: int
    line_total_usd: float


@dataclass(frozen=True, slots=True)
class CartSummary:
    """Cart contents plus the catalog-priced total (see contracts/ui-dsl.md)."""

    lines: tuple[CartLine, ...]
    total_usd: float


def _require_product(catalog: Sequence[Product], product_id: str) -> Product:
    """Return the catalog record for ``product_id``; raise KeyError if unknown.

    Pure lookup — the catalog is never mutated.
    """
    for product in catalog:
        if product.id == product_id:
            return product
    raise KeyError(product_id)


def _coerce_quantity(quantity: int | float, *, minimum: int) -> int:
    """Coerce ``quantity`` to an ``int >= minimum``; raise ValueError otherwise.

    Accepted: ``int`` values and integral ``float`` values (e.g. ``2.0``),
    which LLM tool payloads may emit despite the ``int`` contract. Rejected
    with ``ValueError``: ``bool`` (an ``int`` subclass, but never a valid
    quantity), non-integral floats (``1.5``), and any other type (including
    numeric strings). Deterministic: same input, same outcome.
    """
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        raise ValueError(f"quantity must be an integer, got {quantity!r}")
    coerced = int(quantity)
    if isinstance(quantity, float) and not quantity.is_integer():
        raise ValueError(f"quantity must be a whole number, got {quantity!r}")
    if coerced < minimum:
        raise ValueError(f"quantity must be >= {minimum}, got {coerced}")
    return coerced


def _copied(line: CartItem) -> CartItem:
    """Return a fresh dict with the same content as ``line`` (no aliasing)."""
    return CartItem(product_id=line["product_id"], quantity=int(line["quantity"]))


def add_to_cart(
    cart: Sequence[CartItem],
    catalog: Sequence[Product],
    product_id: str,
    quantity: int = 1,
) -> list[CartItem]:
    """Return a NEW cart with ``quantity`` more of ``product_id`` added.

    Pure and deterministic — ``cart`` is never mutated. Adding to a product
    already in the cart merges into that line (its position is preserved);
    otherwise a new line is appended. The resulting per-line quantity is
    clamped to :data:`MAX_QUANTITY`.

    Args:
        cart: Current cart lines, ``{"product_id": str, "quantity": int}``.
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_id: Stable slug, e.g. ``"aurora-hush-pro"``.
        quantity: How many units to add; must coerce to an ``int >= 1``.

    Returns:
        A new cart list (fresh line dicts throughout).

    Raises:
        ValueError: If ``quantity`` is not coercible to an ``int >= 1``.
        KeyError: If ``product_id`` is not in ``catalog`` (payload is
            ``product_id``).
    """
    amount = _coerce_quantity(quantity, minimum=1)
    _require_product(catalog, product_id)

    merged: list[CartItem] = []
    merged_existing = False
    for line in cart:
        if line["product_id"] == product_id:
            total = min(int(line["quantity"]) + amount, MAX_QUANTITY)
            merged.append(CartItem(product_id=product_id, quantity=total))
            merged_existing = True
        else:
            merged.append(_copied(line))
    if not merged_existing:
        merged.append(CartItem(product_id=product_id, quantity=min(amount, MAX_QUANTITY)))
    return merged


def remove_from_cart(
    cart: Sequence[CartItem],
    catalog: Sequence[Product],
    product_id: str,
) -> list[CartItem]:
    """Return a NEW cart without the ``product_id`` line (pure, idempotent).

    Removing a line that is not present returns an equal, detached copy of the
    cart — no error. The product id is still validated against the catalog,
    so typos surface immediately.

    Args:
        cart: Current cart lines.
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_id: Stable slug of the line to drop.

    Returns:
        A new cart list (fresh line dicts throughout) without the line.

    Raises:
        KeyError: If ``product_id`` is not in ``catalog`` (payload is
            ``product_id``).
    """
    _require_product(catalog, product_id)
    return [_copied(line) for line in cart if line["product_id"] != product_id]


def set_quantity(
    cart: Sequence[CartItem],
    catalog: Sequence[Product],
    product_id: str,
    quantity: int,
) -> list[CartItem]:
    """Return a NEW cart with ``product_id``'s quantity set (pure).

    Semantics: ``0`` removes the line (so ``0`` on an absent line is an
    idempotent no-op); ``1..MAX_QUANTITY`` sets the quantity; larger values
    are clamped to :data:`MAX_QUANTITY`. Setting a positive quantity for a
    product not currently in the cart appends the line (the postcondition is
    simply "the cart contains ``product_id`` at the requested quantity").

    Args:
        cart: Current cart lines.
        catalog: Validated products, as produced by ``app.catalog.loader``.
        product_id: Stable slug of the line to update.
        quantity: Target quantity; must coerce to an ``int >= 0``.

    Returns:
        A new cart list (fresh line dicts throughout).

    Raises:
        ValueError: If ``quantity`` is not coercible to an ``int >= 0``.
        KeyError: If ``product_id`` is not in ``catalog`` (payload is
            ``product_id``).
    """
    target = min(_coerce_quantity(quantity, minimum=0), MAX_QUANTITY)
    _require_product(catalog, product_id)

    result: list[CartItem] = []
    line_present = False
    for line in cart:
        if line["product_id"] == product_id:
            if target > 0:
                result.append(CartItem(product_id=product_id, quantity=target))
            line_present = True
        else:
            result.append(_copied(line))
    if not line_present and target > 0:
        result.append(CartItem(product_id=product_id, quantity=target))
    return result


def get_cart(cart: Sequence[CartItem], catalog: Sequence[Product]) -> CartSummary:
    """Price the cart against the catalog: line totals plus the grand total.

    Pure and deterministic — preserves cart order, rounds every line total and
    the grand total to 2 decimals (the total is the sum of the rounded line
    totals, so displayed lines always add up to the displayed total).

    Args:
        cart: Current cart lines.
        catalog: Validated products, as produced by ``app.catalog.loader``.

    Returns:
        A :class:`CartSummary`; an empty cart yields ``lines=()`` and
        ``total_usd=0.0``.

    Raises:
        KeyError: If a cart line references a product id missing from the
            catalog. A corrupt cart is a programming error, not a recoverable
            condition.
    """
    prices = {product.id: product.price_usd for product in catalog}
    lines: list[CartLine] = []
    for line in cart:
        product_id = line["product_id"]
        if product_id not in prices:
            raise KeyError(product_id)
        quantity = int(line["quantity"])
        lines.append(
            CartLine(
                product_id=product_id,
                quantity=quantity,
                line_total_usd=round(prices[product_id] * quantity, 2),
            )
        )
    total = round(sum(line.line_total_usd for line in lines), 2)
    return CartSummary(lines=tuple(lines), total_usd=total)


__all__ = [
    "MAX_QUANTITY",
    "CartItem",
    "CartLine",
    "CartSummary",
    "add_to_cart",
    "get_cart",
    "remove_from_cart",
    "set_quantity",
]
