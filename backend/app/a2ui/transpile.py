"""A2UI v0.9 projection of the UI-plan DSL (DECISIONS.md D10).

Pure, deterministic transpilation of a SERIALIZED wire plan (camelCase dict,
exactly what ``ui_update`` carries) into an A2UI v0.9 message stream
(``createSurface`` / ``updateComponents`` / ``updateDataModel`` /
``deleteSurface``; specification at github.com/a2ui-project/a2ui). The frozen
DSL contract stays the single source of truth — this module is a PROJECTION,
never a second contract: given the same plan it always produces the same
messages, and a projection failure must never fail a turn whose plan is valid
(the emission site catches and skips).

Composition rules (basic catalog, 18 components; only these are used):
``Card`` (root, single ``child``) → ``Column``/``Row`` layout → ``Text``
variants (``h3``/``body``/``caption``), ``List`` ChildList templates for
repeated data, and ``Button`` for every plan action.

Action wiring is lossless: a ``Button``'s ``action.event`` carries
``name = action.type`` and ``context = {**payload, "label": action.label}``
(static contexts) or per-row bindings for grid cards (``productId`` bound to
the row item's ``id``, mirroring the native renderer's per-card stamping).
Reconstructing ``{type: name, label: context.label, payload: context minus
label}`` after resolving bindings yields the verbatim plan action. Plan action
payloads never contain a ``label`` key (the DSL's six action kinds are fixed),
so the ``label`` context key cannot collide.

Wire version is pinned to ``v0.9`` (v0.9.1 only changed the MIME type and
surface-id uniqueness rules; v1.0 is a breaking release candidate — when it
lands, bump :data:`A2UI_VERSION` and regenerate the golden fixtures).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "A2UI_VERSION",
    "SHOPPING_CATALOG_ID",
    "plan_to_a2ui_messages",
    "surface_id",
]

#: Pinned protocol version of every emitted message (see module docstring).
A2UI_VERSION: str = "v0.9"

#: Identifier of the catalog our components come from (the A2UI basic catalog
#: composition rules; an identifier string, not a resolvable URL — the client
#: renderer decides how to map it).
SHOPPING_CATALOG_ID: str = "https://agentic-shop.local/a2ui/catalogs/shopping/v1.json"

_REVIEW_KEYS: tuple[str, ...] = ("comfort", "anc", "sound", "battery", "value")


def surface_id(session_id: str, turn_id: int) -> str:
    """One A2UI surface per transcript turn (session ids are unique per plan)."""
    return f"{session_id}-{turn_id}"


def plan_to_a2ui_messages(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project one serialized UI plan into its A2UI v0.9 message stream.

    Order is fixed: an optional ``deleteSurface`` for the cart amendment
    (D2 amendment), ``createSurface`` for this turn, ``updateComponents``,
    then ``updateDataModel`` when the composition binds data. Deterministic:
    identical plans produce identical messages.
    """
    session_id = str(plan["sessionId"])
    turn_id = int(plan["turnId"])
    current = surface_id(session_id, turn_id)

    messages: list[dict[str, Any]] = []
    amends = plan.get("amendsTurnId")
    if amends is not None:
        messages.append(
            {
                "version": A2UI_VERSION,
                "deleteSurface": {"surfaceId": surface_id(session_id, int(amends))},
            }
        )

    messages.append(
        {
            "version": A2UI_VERSION,
            "createSurface": {"surfaceId": current, "catalogId": SHOPPING_CATALOG_ID},
        }
    )

    root = plan["root"]
    builder = {
        "product_grid": _grid_components,
        "preference_picker": _picker_components,
        "comparison_table": _comparison_components,
        "product_details": _details_components,
        "cart_view": _cart_components,
        "text_block": _text_block_components,
    }[root["type"]]
    components, data = builder(root["props"], root.get("actions") or [])

    messages.append(
        {
            "version": A2UI_VERSION,
            "updateComponents": {"surfaceId": current, "components": components},
        }
    )
    if data:
        messages.append(
            {"version": A2UI_VERSION, "updateDataModel": {"surfaceId": current, "value": data}}
        )
    return messages


# ---------------------------------------------------------------------------
# Shared composition helpers
# ---------------------------------------------------------------------------


def _card(body_children: list[str]) -> list[dict[str, Any]]:
    """``root`` Card wrapping one ``body`` Column with *body_children*."""
    return [
        {"id": "root", "component": "Card", "child": "body"},
        {"id": "body", "component": "Column", "children": body_children},
    ]


def _button(
    index: int, prefix: str, action: Mapping[str, Any], context: dict[str, Any]
) -> list[dict[str, Any]]:
    """A labeled Button whose event round-trips to the verbatim plan action."""
    return [
        {
            "id": f"{prefix}-text-{index}",
            "component": "Text",
            "text": str(action["label"]),
        },
        {
            "id": f"{prefix}-{index}",
            "component": "Button",
            "child": f"{prefix}-text-{index}",
            "action": {"event": {"name": action["type"], "context": context}},
        },
    ]


def _action_context(action: Mapping[str, Any]) -> dict[str, Any]:
    """``{**payload, "label": label}`` — the lossless context shape."""
    context: dict[str, Any] = dict(action.get("payload") or {})
    context["label"] = action["label"]
    return context


# ---------------------------------------------------------------------------
# product_grid — the flagship: ChildList template + data-model binding
# ---------------------------------------------------------------------------


def _grid_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = {item["id"]: item for item in props.get("products") or []}
    products = [dict(snapshot.get(pid) or {"id": pid}) for pid in props["productIds"]]
    data: dict[str, Any] = {
        "title": props["title"],
        "caption": "Ranked in recommendation order" if props.get("ranked") else "Matching products",
        "products": products,
    }
    # Per-card actions are details/add_to_cart — the native renderer stamps
    # productId at tap time; ``compare`` is grid-level (no product stamping).
    card_actions = [action for action in actions if action["type"] != "compare"]
    grid_actions = [action for action in actions if action["type"] == "compare"]

    row_children = [
        "product-name",
        "product-price",
        "product-anc",
        *(f"card-action-{index}" for index in range(len(card_actions))),
    ]
    components = _card(
        [
            "grid-title",
            "grid-caption",
            "product-list",
            *(f"grid-action-{index}" for index in range(len(grid_actions))),
        ]
    )
    components += [
        {"id": "grid-title", "component": "Text", "text": {"path": "/title"}, "variant": "h3"},
        {
            "id": "grid-caption",
            "component": "Text",
            "text": {"path": "/caption"},
            "variant": "caption",
        },
        {
            "id": "product-list",
            "component": "List",
            "children": {"componentId": "product-row", "path": "/products"},
        },
        {"id": "product-row", "component": "Row", "children": row_children},
        {"id": "product-name", "component": "Text", "text": {"path": "name"}},
        {"id": "product-price", "component": "Text", "text": {"path": "priceUsd"}},
        {
            "id": "product-anc",
            "component": "Text",
            "text": {"path": "ancType"},
            "variant": "caption",
        },
    ]
    for index, action in enumerate(card_actions):
        components += _button(
            index,
            "card-action",
            action,
            {
                # Relative binding: inside the row template this resolves to
                # the current product's id — exactly the native withProduct
                # stamping — while the label round-trips statically.
                "productId": {"path": "id"},
                "label": action["label"],
            },
        )
    for index, action in enumerate(grid_actions):
        components += _button(index, "grid-action", action, _action_context(action))
    return components, data


# ---------------------------------------------------------------------------
# preference_picker — one button per option (options are few and their
# action payloads/labels are per-option, so static beats a shared template)
# ---------------------------------------------------------------------------


def _picker_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    options: list[str] = list(props["options"])
    leftover = actions[len(options) :] if len(actions) > len(options) else []
    components = _card(
        [
            "picker-question",
            *(f"option-{index}" for index in range(len(options))),
            *(f"extra-{index}" for index in range(len(leftover))),
        ]
    )
    components.append(
        {"id": "picker-question", "component": "Text", "text": props["question"], "variant": "h3"}
    )
    for index, option in enumerate(options):
        action = actions[index] if index < len(actions) else None
        components.append({"id": f"option-text-{index}", "component": "Text", "text": option})
        if action is not None:
            components.append(
                {
                    "id": f"option-{index}",
                    "component": "Button",
                    "child": f"option-text-{index}",
                    "action": {
                        "event": {"name": action["type"], "context": _action_context(action)}
                    },
                }
            )
        else:
            components.append({"id": f"option-{index}", "component": "Text", "text": ""})
    for index, action in enumerate(leftover):
        components += _button(index, "extra", action, _action_context(action))
    return components, {}


# ---------------------------------------------------------------------------
# comparison_table — static rows (≤3 products), exact per-row choose labels
# ---------------------------------------------------------------------------


def _comparison_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    product_ids: list[str] = list(props["productIds"])
    attributes: list[str] = list(props["attributes"])
    values: Mapping[str, Mapping[str, Any]] = props.get("values") or {}

    choose_actions: dict[str, Mapping[str, Any]] = {}
    leftovers: list[Mapping[str, Any]] = []
    for action in actions:
        product_id = (action.get("payload") or {}).get("productId")
        if product_id in product_ids:
            choose_actions[str(product_id)] = action
        else:
            leftovers.append(action)

    header_ids = [f"comparison-header-{index}" for index in range(len(attributes) + 1)]
    row_ids = [f"comparison-row-{index}" for index in range(len(product_ids))]
    components = _card([*header_ids, *row_ids, *(f"extra-{i}" for i in range(len(leftovers)))])
    components.append(
        {
            "id": "comparison-header-0",
            "component": "Text",
            "text": "Product",
            "variant": "caption",
        }
    )
    for index, attribute in enumerate(attributes):
        components.append(
            {
                "id": f"comparison-header-{index + 1}",
                "component": "Text",
                "text": attribute,
                "variant": "caption",
            }
        )
    for row_index, product_id in enumerate(product_ids):
        row_children = [f"comparison-cell-{row_index}-0"]
        components.append(
            {"id": f"comparison-cell-{row_index}-0", "component": "Text", "text": product_id}
        )
        product_values = values.get(product_id) or {}
        for attribute_index, attribute in enumerate(attributes):
            cell_id = f"comparison-cell-{row_index}-{attribute_index + 1}"
            row_children.append(cell_id)
            raw = product_values.get(attribute, "—")
            components.append({"id": cell_id, "component": "Text", "text": _cell_text(raw)})
        action = choose_actions.get(product_id)
        if action is not None:
            row_children.append(f"comparison-choose-{row_index}")
            components += _button(row_index, "comparison-choose", action, _action_context(action))
        components.append(
            {"id": f"comparison-row-{row_index}", "component": "Row", "children": row_children}
        )
    for index, action in enumerate(leftovers):
        components += _button(index, "extra", action, _action_context(action))
    return components, {}


def _cell_text(raw: Any) -> str:
    """Human cell text: floats compact, everything else as str."""
    if isinstance(raw, float) and raw.is_integer():
        return f"{int(raw)}"
    return str(raw)


# ---------------------------------------------------------------------------
# product_details
# ---------------------------------------------------------------------------


def _details_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quotes: list[str] = list(props.get("quotes") or [])
    show_quotes = bool(props.get("showQuotes")) and bool(quotes)
    data: dict[str, Any] = {
        "name": props.get("productName") or props["productId"],
        "brand": props.get("brand") or "",
        "quotes": [{"text": quote} for quote in quotes] if show_quotes else [],
    }

    spec_lines = [
        f"Price: ${_fmt(props['priceUsd'])}" if props.get("priceUsd") is not None else None,
        f"Battery: {_fmt(props['batteryHours'])} h"
        if props.get("batteryHours") is not None
        else None,
        f"Weight: {_fmt(props['weightG'])} g" if props.get("weightG") is not None else None,
        f"ANC: {props['ancType']}" if props.get("ancType") else None,
        f"Driver: {_fmt(props['driverMm'])} mm" if props.get("driverMm") is not None else None,
        f"Codecs: {', '.join(props['codecs'])}" if props.get("codecs") else None,
        "Multipoint: yes" if props.get("multipoint") else None,
        "Folding: yes" if props.get("folding") else None,
    ]
    scores = props.get("reviewScores") or {}
    if scores:
        rendered = ", ".join(f"{key} {_fmt(scores[key])}" for key in _REVIEW_KEYS if key in scores)
        spec_lines.append(f"Reviews: {rendered}")

    body_children = ["details-name", "details-brand"]
    body_children += [f"details-spec-{index}" for index, line in enumerate(spec_lines) if line]
    if show_quotes:
        body_children += ["quote-list"]
    body_children += [f"extra-{index}" for index in range(len(actions))]

    components = _card(body_children)
    components += [
        {"id": "details-name", "component": "Text", "text": {"path": "/name"}, "variant": "h3"},
        {
            "id": "details-brand",
            "component": "Text",
            "text": {"path": "/brand"},
            "variant": "caption",
        },
    ]
    spec_index = 0
    for line in spec_lines:
        if line is None:
            continue
        components.append({"id": f"details-spec-{spec_index}", "component": "Text", "text": line})
        spec_index += 1
    if show_quotes:
        components += [
            {
                "id": "quote-list",
                "component": "List",
                "children": {"componentId": "quote-row", "path": "/quotes"},
            },
            {"id": "quote-row", "component": "Row", "children": ["quote-text"]},
            {
                "id": "quote-text",
                "component": "Text",
                "text": {"path": "text"},
                "variant": "caption",
            },
        ]
    for index, action in enumerate(actions):
        components += _button(index, "extra", action, _action_context(action))
    return components, data


def _fmt(value: Any) -> str:
    """Compact number formatting: ``179.0`` -> ``179``, ``4.5`` -> ``4.5``."""
    number = float(value)
    return f"{number:g}"


# ---------------------------------------------------------------------------
# cart_view — static rows, per-row remove buttons, amendment via deleteSurface
# ---------------------------------------------------------------------------


def _cart_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[Mapping[str, Any]] = list(props["items"])
    remove_actions: dict[str, Mapping[str, Any]] = {}
    leftovers: list[Mapping[str, Any]] = []
    for action in actions:
        product_id = (action.get("payload") or {}).get("productId")
        if product_id is not None and any(item["productId"] == product_id for item in items):
            remove_actions[str(product_id)] = action
        else:
            leftovers.append(action)

    row_ids = [f"cart-row-{index}" for index in range(len(items))]
    components = _card([*row_ids, "cart-total", *(f"extra-{i}" for i in range(len(leftovers)))])
    for index, item in enumerate(items):
        row_children = [f"cart-item-{index}", f"cart-qty-{index}"]
        components += [
            {
                "id": f"cart-item-{index}",
                "component": "Text",
                "text": str(item["productId"]),
            },
            {
                "id": f"cart-qty-{index}",
                "component": "Text",
                "text": f"× {int(item['quantity'])}",
                "variant": "caption",
            },
        ]
        action = remove_actions.get(str(item["productId"]))
        if action is not None:
            row_children.append(f"cart-remove-{index}")
            components += _button(index, "cart-remove", action, _action_context(action))
        components.append({"id": f"cart-row-{index}", "component": "Row", "children": row_children})
    components.append(
        {"id": "cart-total", "component": "Text", "text": f"Total: ${_fmt(props['totalUsd'])}"}
    )
    for index, action in enumerate(leftovers):
        components += _button(index, "extra", action, _action_context(action))
    return components, {}


# ---------------------------------------------------------------------------
# text_block
# ---------------------------------------------------------------------------


def _text_block_components(
    props: Mapping[str, Any], actions: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    heading = props.get("heading")
    body_children = (["text-heading"] if heading else []) + [
        "text-body",
        *(f"extra-{index}" for index in range(len(actions))),
    ]
    components = _card(body_children)
    if heading:
        components.append(
            {"id": "text-heading", "component": "Text", "text": str(heading), "variant": "h3"}
        )
    components.append({"id": "text-body", "component": "Text", "text": props["body"]})
    for index, action in enumerate(actions):
        components += _button(index, "extra", action, _action_context(action))
    return components, {}
