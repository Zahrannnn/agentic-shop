"""LangGraph session state for the shopping agent (data-model.md).

:class:`ShoppingState` is the single ``StateGraph`` state schema. All channels
are plain overwrite channels (``LastValue``): every node returns a *partial*
dict and each returned key fully replaces the previous value, so nodes must
merge (e.g. ``intent``, ``messages``) before returning. The ``TypedDict`` is
declared ``total=False`` because partial updates are the norm.

The catalog is intentionally NOT part of the state (it is static, validated
once per process, and must not be checkpointed); nodes read it through
:func:`app.graph.nodes.get_catalog`.

``intent`` shape (plain dict mirroring ``UserIntent`` from data-model.md, kept
as a dict for easy cross-turn merging)::

    {
        "category": str | None,            # known catalog category when set
        "budget_usd": float | None,        # > 0 when stated/derived
        "use_case": str | None,            # free text, e.g. "long flights"
        "priorities": dict[str, float],    # attribute name -> salience 0..1
        "assumptions": list[str],          # disclosed assumptions (budget cap,
                                           # relaxed filters, defaults)
        "flag_contradiction": bool,        # constraints cannot all be satisfied
        "min_battery_hours": float | None, # rule-parsed hard filter (US2)
        "codecs": list[str],               # rule-parsed required codecs (US2)
    }

Other keys:

* ``messages`` — transcript entries ``{"role": "user" | "assistant", "content": str}``.
* ``researched`` — per-product review digests built by the ``research`` node:
  ``{"id": str, "name": str, "highlights": list[str]}`` (deterministic templates
  over pre-scored review data — no runtime NLP, FR-005).
* ``weights`` — the raw ``PreferenceWeights`` mapping used by the last ranking.
* ``followup`` — ``{"kind": str, "product_ids": list[str], "disclosure": str | None}``
  when the intent node resolved the turn as a deterministic follow-up (US4:
  compare / details / add_to_cart / remove_from_cart / cart_view / disclosure);
  ``None`` on normal pipeline turns. Set (or explicitly reset) EVERY turn by
  ``intent_node`` — channels are ``LastValue``, so an absent key would leak a
  stale follow-up into the next turn.
* ``error`` — ``{"message": str, "code": str}`` when a node fails the turn
  cleanly (e.g. plan validation); ``respond`` then ends quietly and the API
  layer omits ``turn_end`` (the already-emitted ``error`` frame is terminal).
* ``turn_id`` — count of completed plan turns; ``ui_plan`` stamps
  ``turn_id + 1`` into the new plan envelope (no wall clock — determinism).
* ``cart_plan_turn_id`` — the ``turnId`` of the FIRST ``cart_view`` plan a
  cart mutation emitted in this session (D2 amendment anchor). Set once, by
  ``_build_followup_plan``, and never overwritten: every later cart turn
  stamps ``amendsTurnId`` with it so the client updates that one cart region
  in place instead of appending duplicate cart sections. ``None`` until the
  first cart mutation.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ShoppingState(TypedDict, total=False):
    """Accumulated per-session state; keyed on ``thread_id`` = session id."""

    # -- turn inputs --------------------------------------------------------
    pending_user_text: str
    pending_ui_action: dict[str, Any] | None
    session_id: str

    # -- conversation & accumulated understanding ---------------------------
    messages: list[dict[str, str]]
    intent: dict[str, Any]
    asked_clarification: bool

    # -- pipeline artifacts --------------------------------------------------
    candidates: list[Any]
    researched: list[dict[str, Any]]
    ranked: list[Any]
    weights: dict[str, float]
    followup: dict[str, Any] | None
    selected_ids: list[str]
    plan: dict[str, Any] | None
    cart: list[dict[str, Any]]
    turn_id: int
    cart_plan_turn_id: int | None

    # -- failure signal ------------------------------------------------------
    error: dict[str, Any] | None
