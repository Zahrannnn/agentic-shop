"""A2UI projection package (DECISIONS.md D10): UI plans → A2UI v0.9 messages."""

from app.a2ui.transpile import A2UI_VERSION, SHOPPING_CATALOG_ID, plan_to_a2ui_messages, surface_id

__all__ = [
    "A2UI_VERSION",
    "SHOPPING_CATALOG_ID",
    "plan_to_a2ui_messages",
    "surface_id",
]
