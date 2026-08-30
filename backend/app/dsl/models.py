"""UI plan DSL models (Pydantic v2) — the agent→frontend contract.

Wire format is camelCase JSON (see ``specs/001-backend-agent-scaffold/contracts/ui-dsl.md``);
internal Python stays snake_case via ``alias_generator=to_camel`` with
``populate_by_name=True``. Every model serializes with
``model_dump(by_alias=True, exclude_none=True)`` (see ``app.dsl.validate``).

The plan is data only (PRD §14): no executable content, flat registry, no
nested children. Validation split: structural/bounds rules live here in
Pydantic; catalog-aware rules live in ``app/dsl/validate.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

ComponentType = Literal[
    "product_grid",
    "preference_picker",
    "comparison_table",
    "product_details",
    "cart_view",
    "text_block",
]

ActionType = Literal[
    "compare",
    "details",
    "select_preference",
    "add_to_cart",
    "remove_from_cart",
    "choose",
]

#: Actions each component type may carry (contracts/ui-dsl.md rule 4).
#: ``cart_view`` keeps ``remove_from_cart`` — the contract's cart_view wire
#: example ships it and the ``cart-one-item`` fixture depends on it.
ALLOWED_ACTIONS: dict[str, set[str]] = {
    "product_grid": {"compare", "details", "add_to_cart"},
    "preference_picker": {"select_preference"},
    "comparison_table": {"choose"},
    "product_details": set(),
    "cart_view": {"remove_from_cart"},
    "text_block": set(),
}

#: Comparison-table attribute whitelist (catalog attribute names + pre-scored
#: review attributes). Anything else is rejected before emission.
ALLOWED_ATTRIBUTES: set[str] = {
    "price_usd",
    "battery_hours",
    "weight_g",
    "anc_type",
    "driver_mm",
    "comfort",
    "anc",
    "sound",
    "battery",
    "value",
    "multipoint",
    "folding",
}


class UIAction(BaseModel):
    """A frontend affordance the client echoes back in ``ChatRequest.ui_action``."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    type: ActionType
    label: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class GridProduct(BaseModel):
    """One card snapshot inside a ``product_grid``: enough for an ecommerce
    card without a catalog lookup."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    price_usd: float
    anc_type: str


class ProductGridProps(BaseModel):
    """Props for ``product_grid``; ``ranked=True`` means product_ids are in
    recommendation order. ``products`` is an optional per-card snapshot keyed
    1:1 with ``product_ids`` (ecommerce cards render names and prices from
    it); keys must match ``product_ids`` exactly when present."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str
    product_ids: list[str] = Field(min_length=1, max_length=6)
    ranked: bool
    products: list[GridProduct] | None = None


class PreferencePickerProps(BaseModel):
    """Props for ``preference_picker`` (clarify chips). Min 2 options so the
    category ask ("Headphones" / "Something else") fits the normal 3-4 bound."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    question: str
    options: list[str] = Field(min_length=2, max_length=4)


class ComparisonTableProps(BaseModel):
    """Props for ``comparison_table``; attributes restricted to
    :data:`ALLOWED_ATTRIBUTES` (checked in ``app/dsl/validate.py``).
    ``values`` is an optional render aid: ``{productId: {attribute: value}}``
    so the client can show real numbers without a catalog lookup. When present,
    its keys must be a subset of ``product_ids``."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_ids: list[str] = Field(min_length=2, max_length=3)
    attributes: list[str] = Field(min_length=1)
    values: dict[str, dict[str, Any]] | None = None


class ProductDetailsProps(BaseModel):
    """Props for ``product_details``; ``show_quotes`` toggles review quotes.
    The catalog snapshot fields (name/brand/price/attributes/scores) travel
    with the plan so the client renders a complete card without a lookup."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_id: str
    show_quotes: bool
    product_name: str | None = None
    brand: str | None = None
    price_usd: float | None = None
    battery_hours: float | None = None
    weight_g: float | None = None
    anc_type: str | None = None
    driver_mm: float | None = None
    codecs: list[str] | None = None
    multipoint: bool | None = None
    folding: bool | None = None
    review_scores: dict[str, float] | None = None
    quotes: list[str] | None = None


class CartLine(BaseModel):
    """One cart row; quantity clamped to 1-10."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_id: str
    quantity: int = Field(ge=1, le=10)


class CartViewProps(BaseModel):
    """Props for ``cart_view``; totals come from catalog prices only."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[CartLine]
    total_usd: float = Field(ge=0.0)


class TextBlockProps(BaseModel):
    """Props for ``text_block`` (assumption/contradiction disclosures)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    body: str
    heading: str | None = None


#: Registry mapping node type -> the props class it must carry. Used by
#: :class:`ComponentNode` to enforce that, e.g., a ``product_grid`` node's
#: props ARE ``ProductGridProps``.
_PROPS_BY_TYPE: dict[str, type[BaseModel]] = {
    "product_grid": ProductGridProps,
    "preference_picker": PreferencePickerProps,
    "comparison_table": ComparisonTableProps,
    "product_details": ProductDetailsProps,
    "cart_view": CartViewProps,
    "text_block": TextBlockProps,
}


class ComponentNode(BaseModel):
    """Exactly one root component per plan; flat registry, no children.

    ``props`` is a smart union; the after-validator pins it to the class
    required by ``type`` (a true Pydantic discriminated union is impossible
    here because the wire ``props`` dict carries no discriminator tag — the
    tag lives on the sibling ``type`` field).
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    type: ComponentType
    props: (
        ProductGridProps
        | PreferencePickerProps
        | ComparisonTableProps
        | ProductDetailsProps
        | CartViewProps
        | TextBlockProps
    )
    actions: list[UIAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _props_match_type(self) -> ComponentNode:
        """Reject nodes whose props type does not match the declared component type."""
        expected = _PROPS_BY_TYPE[self.type]
        if not isinstance(self.props, expected):
            raise ValueError(
                f"component type {self.type!r} requires props of type "
                f"{expected.__name__}, got {type(self.props).__name__}"
            )
        return self


class UIPlan(BaseModel):
    """Plan envelope (wire format): full replace every turn (D2).

    Bounded amendment exception (D2 amendment): a ``cart_view`` plan MAY carry
    ``amends_turn_id`` — the ``turnId`` of the earlier cart plan turn it
    supersedes in place. Everything else stays strict full-replace; catalog
    rules in ``app.dsl.validate`` reject the field on any other root type.
    Serialized with ``exclude_none=True``, so the field is simply absent from
    the wire document when unset (the fixtures stay byte-identical).
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    plan_version: Literal["1"]
    session_id: str = Field(min_length=1)
    turn_id: int = Field(ge=1)
    amends_turn_id: int | None = Field(default=None, ge=1)
    root: ComponentNode
