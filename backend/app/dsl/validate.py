"""Catalog-aware validation and serialization for UI plans.

Structural rules (bounds, literals, shapes) are enforced by the Pydantic
models in :mod:`app.dsl.models`. This module adds the checks Pydantic cannot
express — every referenced product must exist in the catalog, actions must be
within the per-type allowed set, picker chips must be wired to actions,
comparison attributes must be whitelisted — plus the single serialization
entry point used before any ``ui_update`` emission (FR-008/SC-004).

All functions here are pure: no I/O, no state, deterministic.
"""

from __future__ import annotations

from typing import Any

from app.dsl.models import (
    ALLOWED_ACTIONS,
    ALLOWED_ATTRIBUTES,
    CartViewProps,
    ComparisonTableProps,
    ComponentNode,
    PreferencePickerProps,
    ProductDetailsProps,
    ProductGridProps,
    UIPlan,
)


class PlanValidationError(ValueError):
    """A plan is structurally valid but violates catalog-aware DSL rules."""


#: Action types whose payload may reference a catalog product. ``compare``,
#: ``details`` and ``add_to_cart`` usually ship empty payloads (the component's
#: props carry the ids), but a productId in their payload must still be valid.
#: ``select_preference`` is deliberately excluded — its payload carries free
#: preference values (e.g. ``{"value": "something-else"}``), not product ids.
_PRODUCT_PAYLOAD_ACTIONS: frozenset[str] = frozenset(
    {"compare", "details", "add_to_cart", "choose", "remove_from_cart"}
)

#: Action types that are meaningless without a target product, so the payload
#: MUST carry ``productId``.
_REQUIRES_PRODUCT_PAYLOAD: frozenset[str] = frozenset({"choose", "remove_from_cart"})


def _validate_actions(node: ComponentNode, valid_product_ids: set[str]) -> list[str]:
    """Return error strings for action-set and action-payload violations."""
    errors: list[str] = []
    allowed = ALLOWED_ACTIONS.get(node.type, set())
    for action in node.actions:
        if action.type not in allowed:
            errors.append(
                f"action {action.type!r} is not allowed on component type "
                f"{node.type!r} (allowed: {sorted(allowed)})"
            )
        if action.type in _REQUIRES_PRODUCT_PAYLOAD and "productId" not in action.payload:
            errors.append(f"action {action.type!r} on {node.type!r} requires payload['productId']")
        if action.type in _PRODUCT_PAYLOAD_ACTIONS:
            product_id = action.payload.get("productId")
            if isinstance(product_id, str) and product_id not in valid_product_ids:
                errors.append(
                    f"action {action.type!r} on {node.type!r} references unknown "
                    f"productId {product_id!r}"
                )
    return errors


def _validate_preference_picker(node: ComponentNode, props: PreferencePickerProps) -> list[str]:
    """Return error strings for picker option/action mismatches.

    Every option needs a matching ``select_preference`` action whose label
    equals the option, and no dangling select_preference actions may exist.
    """
    errors: list[str] = []
    labels = {action.label for action in node.actions if action.type == "select_preference"}
    missing = [option for option in props.options if option not in labels]
    if missing:
        errors.append(
            f"preference_picker options without a matching select_preference action: {missing}"
        )
    dangling = sorted(labels - set(props.options))
    if dangling:
        errors.append(
            f"preference_picker has select_preference actions whose labels are "
            f"not options: {dangling}"
        )
    return errors


def _validate_comparison(node: ComponentNode, props: ComparisonTableProps) -> list[str]:
    """Return error strings for attribute-whitelist and choose-count violations."""
    errors: list[str] = []
    unknown = [attr for attr in props.attributes if attr not in ALLOWED_ATTRIBUTES]
    if unknown:
        errors.append(
            f"comparison_table attributes outside the whitelist: {unknown} "
            f"(allowed: {sorted(ALLOWED_ATTRIBUTES)})"
        )
    choose_count = sum(1 for action in node.actions if action.type == "choose")
    if choose_count > 1:
        errors.append(
            f"comparison_table may carry at most one 'choose' action, found {choose_count}"
        )
    if props.values is not None:
        stray = sorted(set(props.values) - set(props.product_ids))
        if stray:
            errors.append(
                f"comparison_table values reference products outside product_ids: {stray}"
            )
        bad_attrs = sorted(
            {
                attr
                for per_product in props.values.values()
                for attr in per_product
                if attr not in ALLOWED_ATTRIBUTES
            }
        )
        if bad_attrs:
            errors.append(f"comparison_table value attributes outside the whitelist: {bad_attrs}")
    return errors


def _validate_props_product_ids(props: Any, valid_product_ids: set[str]) -> list[str]:
    """Return error strings for unknown product ids referenced in props."""
    errors: list[str] = []
    referenced: list[str] = []
    if isinstance(props, (ProductGridProps, ComparisonTableProps)):
        referenced = list(props.product_ids)
    elif isinstance(props, ProductDetailsProps):
        referenced = [props.product_id]
    elif isinstance(props, CartViewProps):
        referenced = [line.product_id for line in props.items]
    unknown = [pid for pid in referenced if pid not in valid_product_ids]
    if unknown:
        errors.append(f"plan references unknown product ids: {sorted(set(unknown))}")
    if isinstance(props, ProductGridProps) and props.products is not None:
        snapshot_ids = [product.id for product in props.products]
        if sorted(snapshot_ids) != sorted(props.product_ids):
            errors.append(
                "product_grid products snapshot must match product_ids exactly: "
                f"{sorted(snapshot_ids)} vs {sorted(props.product_ids)}"
            )
    return errors


def _validate_amendment(plan: UIPlan) -> list[str]:
    """Bounded amendment rule (D2 amendment): only ``cart_view`` roots may
    carry ``amendsTurnId`` in the MVP — everything else is strict full-replace.

    Presence/type (optional int ≥ 1) is enforced by the Pydantic envelope;
    this adds the MVP scope check Pydantic cannot express."""
    if plan.amends_turn_id is not None and plan.root.type != "cart_view":
        return [f"amendsTurnId is only allowed on cart_view plans (MVP), not on {plan.root.type!r}"]
    return []


def validate_plan(plan: UIPlan, valid_product_ids: set[str]) -> UIPlan:
    """Run all catalog-aware checks against ``plan``.

    Args:
        plan: A structurally valid (Pydantic-validated) plan.
        valid_product_ids: Ids that exist in the catalog.

    Returns:
        The same plan instance, unchanged, once every check passes.

    Raises:
        PlanValidationError: With a descriptive message listing every
            violation. A failing plan is never serialized or emitted.
    """
    errors: list[str] = []
    node = plan.root
    errors.extend(_validate_amendment(plan))
    errors.extend(_validate_actions(node, valid_product_ids))
    errors.extend(_validate_props_product_ids(node.props, valid_product_ids))
    if isinstance(node.props, PreferencePickerProps):
        errors.extend(_validate_preference_picker(node, node.props))
    if isinstance(node.props, ComparisonTableProps):
        errors.extend(_validate_comparison(node, node.props))
    if errors:
        raise PlanValidationError(
            f"invalid UI plan (session={plan.session_id!r}, turn={plan.turn_id}): "
            + "; ".join(errors)
        )
    return plan


def serialize_plan(plan: UIPlan) -> dict[str, Any]:
    """Serialize a plan to the camelCase wire format.

    The caller must have validated the plan; this function does not check
    anything (validation and serialization are deliberately separate).

    Returns:
        A JSON-ready dict equivalent to ``model_dump(by_alias=True,
        exclude_none=True)``.
    """
    return plan.model_dump(by_alias=True, exclude_none=True)


def validate_and_serialize(plan: UIPlan, valid_product_ids: set[str]) -> dict[str, Any]:
    """Convenience pipeline: validate, then serialize.

    Raises:
        PlanValidationError: See :func:`validate_plan`.
    """
    return serialize_plan(validate_plan(plan, valid_product_ids))


__all__ = [
    "PlanValidationError",
    "UIPlan",
    "validate_and_serialize",
    "validate_plan",
    "serialize_plan",
]
