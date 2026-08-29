"""Graph nodes: US1 proceed path, US2 clarify gate, US4 follow-ups (D6, R7).

Node contract
-------------
* Every node is a **sync** function returning a *partial* state update; each
  returned key replaces the previous channel value, so mergeable channels
  (``intent``, ``messages``) are merged before returning.
* Lifecycle events reach the API layer as custom stream payloads — plain
  tuples ``(kind, data)`` — emitted through LangGraph's stream writer:

  ``("status", {"stage": ...[, "count": int]})``,
  ``("message_delta", {"text": str})``,
  ``("ui_update", <serialized UI plan dict>)``,
  ``("error", {"message": str, "code": str})``.

  ``app.api.routes`` translates them 1:1 into SSE frames (research R3).
* Every LLM call goes through ``call_structured`` (D8: validate → retry once →
  typed failure) with the sentinel-wrapped context block described in
  :func:`_llm_messages`, keeping mock-mode behavior deterministic.
* No prints, no clock, no randomness: identical inputs produce identical
  emissions (principle III).

US4 follow-up turns are resolved deterministically in the intent node BEFORE
any model call, mirroring the chip fast-path: positional and demonstrative
references ("compare the first two", "add that one to my cart") resolve
against the session's presented products, and the matched turn skips the
intent and narration LLM calls (weights still flow through the normal
pipeline so ``ranked`` stays fresh). The resolver itself lives in
:mod:`app.graph.followups` (pure, unit-testable); this module re-exports its
public names.

The catalog is NOT checkpointed state; nodes read it via :func:`get_catalog`,
a process-wide lazy singleton over ``app.catalog.loader.load_catalog``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import ValidationError

from app.catalog.loader import load_catalog
from app.catalog.models import Product
from app.dsl.models import (
    CartLine,
    CartViewProps,
    ComparisonTableProps,
    ComponentNode,
    PreferencePickerProps,
    ProductDetailsProps,
    ProductGridProps,
    TextBlockProps,
    UIAction,
    UIPlan,
)
from app.dsl.validate import PlanValidationError, serialize_plan, validate_plan
from app.graph.followups import (
    COMPARISON_ATTRIBUTES,
    FOLLOWUP_ACTION_TYPES,
    NO_PRODUCTS_DISCLOSURE,
    TOP_N,
    FollowUp,
    catalog_id_set,
    ranked_ids,
    resolve_followup,
)
from app.graph.schemas import IntentExtraction, Narration, PreferenceWeights
from app.graph.state import ShoppingState
from app.llm.client import CONTEXT_CLOSE, CONTEXT_OPEN, call_structured, get_llm
from app.ranking.scorer import SCORABLE_ATTRIBUTES, ScoredProduct, score_products
from app.tools.cart import add_to_cart, get_cart, remove_from_cart
from app.tools.research import summarize_candidates
from app.tools.search import SearchFilters, relax_filters, search_products

__all__ = [
    "ASK_QUESTION",
    "COMPARISON_ATTRIBUTES",
    "DEFAULT_BUDGET_USD",
    "FOLLOWUP_ACTION_TYPES",
    "FollowUp",
    "NO_PRODUCTS_DISCLOSURE",
    "PLAN_TITLE",
    "clarify_decision",
    "clarify_gate",
    "get_catalog",
    "intent_node",
    "recommend_node",
    "research_node",
    "resolve_followup",
    "respond_node",
    "search_node",
    "ui_agent_ask",
    "ui_plan_node",
]

#: Custom stream payload: ``(kind, data)`` translated 1:1 into an SSE frame.
StreamPayload = tuple[str, Any]

#: How many candidates the research node digests (bounded work at 28 items).
RESEARCH_TOP_N: int = 6

#: Budget cap applied (and disclosed) when the shopper states no budget (R7,
#: US2 scenario 3). Module constant so tests can pin the exact assumption.
DEFAULT_BUDGET_USD: float = 250.0

#: The clarify question — the picker plan's ``question`` prop (US2 / fixture
#: ``preference-picker-category.json``).
ASK_QUESTION: str = "Which category are you shopping for?"

#: The fallback chip label, always offered last in the category ask.
OTHER_OPTION_LABEL: str = "Something else"


# ---------------------------------------------------------------------------
# Catalog singleton + stream writer plumbing
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_catalog() -> tuple[Product, ...]:
    """Load the validated catalog once per process (loaded items are immutable).

    Kept out of :class:`ShoppingState` on purpose: the catalog is static, so
    checkpointing it per thread would only bloat the checkpointer.
    """
    return tuple(load_catalog())


def _emit(payload: StreamPayload) -> None:
    """Forward a custom stream event; a no-op outside a graph run context.

    The guard keeps nodes directly callable (``graph.invoke`` in unit tests)
    where ``get_stream_writer`` raises ``RuntimeError``.
    """
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    if writer is not None:
        writer(payload)


# ---------------------------------------------------------------------------
# Prompt construction (sentinel context block — see app.llm.client)
# ---------------------------------------------------------------------------

_INTENT_SYSTEM_PROMPT = (
    "You parse a shopper's message into structured intent: the product "
    "category, their budget in US dollars, what they will use the product for, "
    "and which product attributes they care about with a salience between 0 "
    "and 1. Fill in only what the user actually stated; leave everything else "
    "unset. Never invent constraints the user did not mention."
)

_WEIGHTS_SYSTEM_PROMPT = (
    "You convert a shopper's stated priorities into preference weights between "
    "0 and 1 for exactly these attributes: battery, comfort, anc, sound, and "
    "value. Louder priorities get higher weights; attributes the shopper never "
    "mentioned get 0. You never see or rank products — weights only."
)

_NARRATION_SYSTEM_PROMPT = (
    "You write the spoken answer for a product recommendation: a one-sentence "
    "intro, one sentence per recommended product that restates ONLY the "
    "highlights provided for that product, and a one-sentence closing "
    "question. Never invent product facts, prices, or numbers."
)


def _llm_messages(system: str, user_text: str, context: dict[str, Any]) -> list[BaseMessage]:
    """Build one LLM call's messages: system prose, user text, context block.

    The final ``HumanMessage`` carries the sentinel-wrapped machine-readable
    context (``<<<CONTEXT>>>{json}<<<END_CONTEXT>>>``) that the mock handlers
    and scripted fakes key on. It must remain the last sentinel-bearing
    message of every call.
    """
    return [
        SystemMessage(content=system),
        HumanMessage(content=user_text),
        HumanMessage(content=f"{CONTEXT_OPEN}{json.dumps(context, sort_keys=True)}{CONTEXT_CLOSE}"),
    ]


# ---------------------------------------------------------------------------
# Small deterministic helpers shared by nodes
# ---------------------------------------------------------------------------


def _coerce_float(value: Any) -> float | None:
    """Best-effort ``float`` coercion; ``None`` for anything non-numeric."""
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return None
    return coerced if math.isfinite(coerced) else None


#: Priority-name aliases -> canonical weight keys. Mirrors the alias table in
#: ``app.llm.client`` (intent merge and mock handling must agree on the five
#: canonical keys) but lives here because merging is graph policy.
_PRIORITY_ALIASES: tuple[tuple[str, str], ...] = (
    ("noise", "anc"),
    ("anc", "anc"),
    ("comfort", "comfort"),
    ("battery", "battery"),
    ("sound", "sound"),
    ("audio", "sound"),
    ("cheap", "value"),
    ("value", "value"),
    ("price", "value"),
)


def _canonical_priority(name: Any) -> str | None:
    """Map an arbitrary priority name onto one of the five weight keys."""
    lowered = str(name).lower().strip()
    for needle, key in _PRIORITY_ALIASES:
        if needle in lowered:
            return key
    return None


def _fmt_price(value: float) -> str:
    """Compact dollar formatting: ``179.0`` -> ``"$179"``, ``189.5`` -> ``"$189.5"``."""
    return f"${value:g}"


def _fmt_score(value: float) -> str:
    """One-decimal review-score formatting: ``4.9`` -> ``"4.9"``."""
    return f"{value:.1f}"


_ANC_LABELS: dict[str, str] = {
    "adaptive": "adaptive ANC",
    "active": "active ANC",
    "passive": "passive isolation",
    "none": "noise isolation",
}

#: Highlight templates per scored attribute (best contribution first).
_CONTRIBUTION_TEMPLATES: dict[str, Callable[[Product], str]] = {
    "battery": lambda p: f"{p.battery_hours:g}h battery",
    "comfort": lambda p: f"comfort rated {_fmt_score(p.review_scores.comfort)}/5",
    "anc": lambda p: (
        f"{_ANC_LABELS.get(str(p.anc_type), 'noise control')} "
        f"rated {_fmt_score(p.review_scores.anc)}/5"
    ),
    "sound": lambda p: f"sound quality rated {_fmt_score(p.review_scores.sound)}/5",
    "value": lambda p: f"reviewers rate the value {_fmt_score(p.review_scores.value)}/5",
    "anc_type": lambda p: f"{_ANC_LABELS.get(str(p.anc_type), 'noise control')} tier",
    "price": lambda p: f"{_fmt_price(p.price_usd)} price point",
    "weight": lambda p: f"{p.weight_g:g} g — light for long sessions",
}


def _highlights(product: Product, scored: ScoredProduct, budget: float | None) -> list[str]:
    """1–3 deterministic narration highlights, best contribution first.

    Grounding comes from the pure scorer's per-attribute contributions plus a
    budget delta — never from generated prose (principle III).
    """
    highlights: list[str] = []
    contributions = sorted(scored.contributions.items(), key=lambda kv: (-kv[1], kv[0]))
    for attr, _contribution in contributions:
        template = _CONTRIBUTION_TEMPLATES.get(attr)
        if template is not None:
            highlights.append(template(product))
        if len(highlights) >= 2:
            break
    if budget is not None and product.price_usd <= budget:
        delta = budget - product.price_usd
        if delta > 0:
            highlights.append(f"{_fmt_price(product.price_usd)} — ${delta:g} under budget")
        else:
            highlights.append(f"{_fmt_price(product.price_usd)} — right at budget")
    return highlights[:3] or ["a strong all-round match"]


def _chunk_words(text: str, words_per_chunk: int = 2) -> list[str]:
    """Split ``text`` into deterministic ``message_delta`` chunks.

    Concatenating the returned chunks reproduces ``text`` exactly (chunks
    after the first carry a leading space).
    """
    words = text.split()
    chunks = [
        " ".join(words[index : index + words_per_chunk])
        for index in range(0, len(words), words_per_chunk)
    ]
    return [chunk if pos == 0 else f" {chunk}" for pos, chunk in enumerate(chunks)]


def _add_assumption(intent: dict[str, Any], text: str) -> None:
    """Append an assumption string once (idempotent across turns).

    ``intent`` accumulates across a session, so a discloser that already fired
    (e.g. the default budget on a later budget-less turn) must not duplicate.
    """
    assumptions = intent.setdefault("assumptions", [])
    if text not in assumptions:
        assumptions.append(text)


# ---------------------------------------------------------------------------
# Rule-based hard-constraint extraction (battery hours, codecs)
# ---------------------------------------------------------------------------

#: "60 hour battery", "70h", "at least 30 hrs" -> minimum battery hours.
_BATTERY_HOURS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hrs|hrs\.|hours|hour)\b", re.IGNORECASE)

#: Codec mentions -> canonical catalog codec slugs, longest/most specific first.
_CODEC_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\baptx[\s_-]?hd\b", "aptx_hd"),
    (r"\baptx\b", "aptx"),
    (r"\bldac\b", "ldac"),
    (r"\blc3\b", "lc3"),
    (r"\baac\b", "aac"),
    (r"\bsbc\b", "sbc"),
)


def _extract_attribute_constraints(text: str) -> dict[str, Any]:
    """Deterministically parse hard attribute constraints from the user text.

    The ``IntentExtraction`` schema carries no battery/codec fields, so these
    hard search constraints are read by fixed rules (never invented by the
    model): minimum battery hours and required codecs. They merge into
    ``intent`` like every other field and therefore accumulate across turns.
    """
    constraints: dict[str, Any] = {}
    if (match := _BATTERY_HOURS_RE.search(text)) is not None:
        hours = _coerce_float(match.group(1))
        if hours is not None and hours > 0:
            constraints["min_battery_hours"] = hours
    lowered = text.lower()
    codecs = [slug for pattern, slug in _CODEC_PATTERNS if re.search(pattern, lowered)]
    if codecs:
        constraints["codecs"] = codecs
    return constraints


# ---------------------------------------------------------------------------
# US4: deterministic follow-up resolution lives in app.graph.followups
# (re-exported above); the intent node resolves follow-ups BEFORE any LLM call.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# intent
# ---------------------------------------------------------------------------


def _merge_intent(existing: dict[str, Any], extraction: IntentExtraction) -> dict[str, Any]:
    """Merge one turn's extraction into the accumulated intent (code, not LLM).

    Rules: a newly stated non-None value replaces the old one; ``None`` never
    clears an existing value; priorities merge by max salience on canonical
    keys; float-ish inputs are coaxed through :func:`_coerce_float`. The
    rule-parsed hard constraints (``min_battery_hours``, ``codecs``) are
    carried forward the same way.
    """
    merged: dict[str, Any] = {
        "category": existing.get("category"),
        "budget_usd": _coerce_float(existing.get("budget_usd")),
        "use_case": existing.get("use_case"),
        "priorities": dict(existing.get("priorities") or {}),
        "assumptions": list(existing.get("assumptions") or []),
        "flag_contradiction": bool(existing.get("flag_contradiction", False)),
        "min_battery_hours": _coerce_float(existing.get("min_battery_hours")),
        "codecs": [str(codec) for codec in (existing.get("codecs") or [])],
    }
    if extraction.category and extraction.category.strip():
        merged["category"] = extraction.category.strip().lower()
    budget = _coerce_float(extraction.budget_usd)
    if budget is not None and budget > 0:
        merged["budget_usd"] = budget
    if extraction.use_case and extraction.use_case.strip():
        merged["use_case"] = extraction.use_case.strip()
    for name, salience in (extraction.priorities or {}).items():
        key = _canonical_priority(name)
        level = _coerce_float(salience)
        if key is None or level is None:
            continue
        level = min(1.0, max(0.0, level))
        merged["priorities"][key] = max(merged["priorities"].get(key, 0.0), level)
    return merged


def _chip_category(action: Any) -> str | None:
    """Return the category a ``select_preference`` chip answer selects, if any.

    Documented choice (US2 answer turn): a category chip IS the intent — the
    value is merged deterministically and the LLM intent call is skipped, so
    the gate outcome never depends on a model. ``other`` / blank / non-chip
    actions return ``None`` and the normal text path runs (the shopper may
    still have typed a category alongside "Something else").
    """
    if not isinstance(action, dict) or action.get("type") != "select_preference":
        return None
    value = (action.get("payload") or {}).get("value")
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    if not cleaned or cleaned == "other":
        return None
    return cleaned


def intent_node(state: ShoppingState) -> dict[str, Any]:
    """Parse the pending user text into intent and append it to the transcript.

    Three paths:

    * chip answer (``select_preference`` with a category value) — the category
      is merged deterministically and the LLM intent call is skipped (see
      :func:`_chip_category`);
    * US4 follow-up (:func:`resolve_followup` matched a ui_action or a
      positional/demonstrative phrase) — the turn is fully determined by
      session state, so the LLM intent call is skipped here too, keeping
      follow-up resolution model-free and deterministic;
    * otherwise the structured intent call runs as usual.

    Either way, the rule-based attribute constraints (battery hours, codecs)
    are parsed from the raw text and merged; they are hard search filters the
    LLM schema does not carry. ``followup`` is set (or explicitly reset to
    ``None``) every turn — channels are LastValue, so omitting the key would
    leak a stale follow-up into the next turn.
    """
    text = state.get("pending_user_text", "")
    action = state.get("pending_ui_action")
    chip_category = _chip_category(action)
    followup = None if chip_category is not None else resolve_followup(state)
    if chip_category is not None:
        intent = _merge_intent(state.get("intent", {}), IntentExtraction())
        intent["category"] = chip_category
    elif followup is not None:
        intent = _merge_intent(state.get("intent", {}), IntentExtraction())
    else:
        extraction = call_structured(
            get_llm(),
            IntentExtraction,
            _llm_messages(_INTENT_SYSTEM_PROMPT, text, {"task": "intent"}),
        )
        intent = _merge_intent(state.get("intent", {}), extraction)
    for key, value in _extract_attribute_constraints(text).items():
        intent[key] = value
    _emit(("status", {"stage": "intent_parsed"}))
    # Transcript entry: the typed text, or a deterministic rendering of a
    # chip-only answer so the conversation stays readable.
    content = text.strip()
    if not content:
        label = action.get("label") if isinstance(action, dict) else None
        content = str(label) if label else f"[selected: {chip_category or 'other'}]"
    messages = [*state.get("messages", []), {"role": "user", "content": content}]
    return {
        "intent": intent,
        "messages": messages,
        "followup": followup.to_state() if followup is not None else None,
    }


# ---------------------------------------------------------------------------
# clarify_gate (US2 — deterministic rule table, research R7)
# ---------------------------------------------------------------------------


def clarify_gate(state: ShoppingState) -> dict[str, Any]:
    """Gate node: a pass-through — the whole rule table lives in the pure
    router :func:`clarify_decision` and the proceed-path policies (budget
    default, contradiction fallback) live in :func:`search_node`."""
    _ = state
    return {}


def _known_categories() -> frozenset[str]:
    """Lowercased catalog category set (pure read via :func:`get_catalog`)."""
    return frozenset(product.category.lower() for product in get_catalog())


def clarify_decision(state: ShoppingState) -> str:
    """Conditional-edge router out of ``clarify_gate`` — R7 rule table, in
    this exact precedence:

    1. a resolved US4 follow-up with unresolvable targets
       (``followup.kind == "disclosure"``) → ``"disclose"``: the turn ends
       cleanly with the deterministic disclosure (bypassing search/research/
       recommend, whose budget/category defaults would otherwise record
       spurious assumptions into the session intent);
    2. ``asked_clarification`` is True → ``"proceed"`` (never ask twice in a
       row; after any answer the pipeline always runs to completion);
    3. ``intent.category`` is missing or not a known catalog category →
       ``"ask"``;
    4. Otherwise → ``"proceed"``.

    Pure: reads only the state dict plus the catalog category set. Missing
    budget or contradictory constraints never ask (R7: don't ask about
    budget; contradictions proceed with disclosed closest matches). A *resolvable*
    follow-up does not take the disclosure route — it rides the normal
    proceed pipeline so ``ranked`` stays fresh.
    """
    followup = state.get("followup")
    if isinstance(followup, dict) and followup.get("kind") == "disclosure":
        return "disclose"
    if state.get("asked_clarification"):
        return "proceed"
    category = (state.get("intent") or {}).get("category")
    if not isinstance(category, str) or not category.strip():
        return "ask"
    if category.strip().lower() not in _known_categories():
        return "ask"
    return "proceed"


def _category_options() -> list[tuple[str, str]]:
    """Deterministic ``(label, value)`` chips for the category ask.

    Catalog categories (deduplicated, sorted, title-cased) plus the
    "Something else" fallback chip, capped at 4 options total — the picker
    bound in the DSL contract.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for product in get_catalog():
        slug = product.category.strip().lower()
        if slug and slug not in seen:
            seen.add(slug)
            pairs.append((slug.replace("_", " ").title(), slug))
    pairs = pairs[:3]  # keep room for the fallback chip (4-option cap)
    pairs.append((OTHER_OPTION_LABEL, "other"))
    return pairs


def ui_agent_ask(state: ShoppingState) -> dict[str, Any]:
    """US2 ask turn: one question, tappable chips, then the turn ends.

    Emits a single ``message_delta`` with the spoken question and builds a
    ``preference_picker`` plan deterministically (never model-written). Same
    fail-clean contract as :func:`ui_plan_node` (US3: every emitted plan is
    validated first): on ``PlanValidationError``/``ValidationError`` the plan
    is never emitted — the turn ends with one ``error`` frame instead.
    """
    options = _category_options()
    category_labels = ", ".join(label for label, value in options if value != "other")
    spoken = f"{ASK_QUESTION} I can help with: {category_labels}."
    _emit(("message_delta", {"text": spoken}))
    try:
        plan = UIPlan(
            plan_version="1",
            session_id=state.get("session_id") or "",
            turn_id=state.get("turn_id", 0) + 1,
            root=ComponentNode(
                type="preference_picker",
                props=PreferencePickerProps(
                    question=ASK_QUESTION,
                    options=[label for label, _value in options],
                ),
                actions=[
                    UIAction(type="select_preference", label=label, payload={"value": value})
                    for label, value in options
                ],
            ),
        )
        validate_plan(plan, {product.id for product in get_catalog()})
    except (PlanValidationError, ValidationError):
        _emit(("error", dict(_PLAN_ERROR_PAYLOAD)))
        return {"error": dict(_PLAN_ERROR_PAYLOAD)}
    serialized = serialize_plan(plan)
    _emit(("ui_update", serialized))
    messages = [*state.get("messages", []), {"role": "assistant", "content": spoken}]
    return {
        "plan": serialized,
        "turn_id": plan.turn_id,
        "asked_clarification": True,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def _relaxation_description(original: SearchFilters, relaxed: SearchFilters) -> str:
    """Human-readable diff of what a relaxation step gave up (deterministic)."""
    changes: list[str] = []
    if original.codecs != relaxed.codecs:
        changes.append("codec requirements")
    if original.require_anc != relaxed.require_anc:
        changes.append("the noise-cancelling requirement")
    if original.min_battery_hours != relaxed.min_battery_hours:
        changes.append("the minimum battery life")
    if original.multipoint != relaxed.multipoint:
        changes.append("the multipoint requirement")
    if original.folding != relaxed.folding:
        changes.append("the folding requirement")
    if original.max_price != relaxed.max_price:
        if relaxed.max_price is None:
            changes.append("the price cap (now no limit)")
        else:
            changes.append(f"the price cap to {_fmt_price(relaxed.max_price)}")
    return " and ".join(changes) if changes else "some constraints"


def _fallback_set(catalog: tuple[Product, ...], category_key: str | None) -> list[Product]:
    """Closest-match fallback: the full category set, else the whole catalog."""
    if category_key:
        subset = [product for product in catalog if product.category.lower() == category_key]
        if subset:
            return subset
    return list(catalog)


def search_node(state: ShoppingState) -> dict[str, Any]:
    """Filter the catalog; on zero hits relax constraints and disclose it.

    Proceed-path policies (R7, US2), all deterministic:

    * missing budget → the :data:`DEFAULT_BUDGET_USD` cap is applied and
      disclosed as an assumption (never a question);
    * hard attribute demands (battery hours / codecs) that no product in the
      category satisfies at ANY price → ``flag_contradiction`` + closest
      matches from the full category set (or whole catalog when the category
      is open), disclosed;
    * otherwise an empty result walks :func:`relax_filters` with a disclosure
      per step; if even the fully relaxed search is empty (e.g. an unknown
      category carried past the gate), the same closest-match fallback fires.
    """
    _emit(("status", {"stage": "searching"}))
    intent = dict(state.get("intent", {}))
    intent["assumptions"] = list(intent.get("assumptions") or [])
    catalog = get_catalog()

    raw_category = intent.get("category")
    category_key = None
    if isinstance(raw_category, str) and raw_category.strip():
        category_key = raw_category.strip().lower()
    if category_key is None:
        _add_assumption(intent, "No category given — showing options from the whole catalog.")

    budget = _coerce_float(intent.get("budget_usd"))
    if budget is None or budget <= 0:
        budget = DEFAULT_BUDGET_USD
        intent["budget_usd"] = budget
        _add_assumption(
            intent,
            f"No budget given — using {_fmt_price(DEFAULT_BUDGET_USD)} as a sensible cap "
            f"for {category_key or 'your search'}.",
        )

    min_battery_hours = _coerce_float(intent.get("min_battery_hours"))
    codecs = tuple(str(codec).lower() for codec in (intent.get("codecs") or []))
    filters = SearchFilters(
        category=category_key,
        max_price=budget,
        min_battery_hours=min_battery_hours,
        codecs=codecs,
    )
    matches = search_products(catalog, filters)
    if not matches:
        has_attr_constraints = bool(filters.min_battery_hours or filters.codecs)
        attribute_matches = (
            search_products(
                catalog,
                SearchFilters(
                    category=category_key,
                    min_battery_hours=min_battery_hours,
                    codecs=codecs,
                ),
            )
            if has_attr_constraints
            else []
        )
        if has_attr_constraints and not attribute_matches:
            # The demanded attributes do not exist in the category at any
            # price: the constraints are contradictory, so relax everything
            # at once and present the closest matches honestly (R7).
            intent["flag_contradiction"] = True
            _add_assumption(
                intent,
                "Your ideal combination isn't available — showing the closest matches.",
            )
            matches = _fallback_set(catalog, category_key)
        else:
            for relaxed in relax_filters(filters):
                matches = search_products(catalog, relaxed)
                if matches:
                    _add_assumption(
                        intent,
                        f"no exact matches — relaxed {_relaxation_description(filters, relaxed)}",
                    )
                    break
            if not matches:
                # Fully relaxed and still empty (unknown category past the
                # gate): fall back to the closest matches rather than an
                # empty screen.
                _add_assumption(
                    intent,
                    "Your ideal combination isn't available — showing the closest matches.",
                )
                matches = _fallback_set(catalog, category_key)
    _emit(("status", {"stage": "found_n", "count": len(matches)}))
    return {"candidates": matches, "intent": intent}


# ---------------------------------------------------------------------------
# research
# ---------------------------------------------------------------------------


def _research_highlights(product: Product) -> list[str]:
    """Deterministic review digests from pre-scored data (no NLP, FR-005)."""
    scores = product.review_scores.model_dump()
    top_attributes = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    highlights = [f"reviewers rate {attr} {_fmt_score(score)}/5" for attr, score in top_attributes]
    highlights.append(f"around {_fmt_price(product.price_usd)}")
    return highlights


def research_node(state: ShoppingState) -> dict[str, Any]:
    """Digest pre-scored reviews for the strongest candidates into state.

    A cheap neutral-weight pre-score bounds the work to the top
    :data:`RESEARCH_TOP_N` candidates; results feed the ``respond`` node via
    the ``researched`` state key.
    """
    _emit(("status", {"stage": "researching"}))
    candidates = state.get("candidates", [])
    catalog = get_catalog()
    pre_weights = dict.fromkeys(SCORABLE_ATTRIBUTES, 0.2)
    pre_scored = score_products(candidates, pre_weights)
    top_ids = [scored.product_id for scored in pre_scored[:RESEARCH_TOP_N]]
    by_id = {product.id: product for product in catalog}
    researched = [
        {
            "id": summary.product_id,
            "name": by_id[summary.product_id].name,
            "highlights": _research_highlights(by_id[summary.product_id]),
        }
        for summary in summarize_candidates(catalog, top_ids)
    ]
    return {"researched": researched}


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


def _fallback_weights(priorities: dict[str, Any]) -> dict[str, float]:
    """Deterministic keyword-map fallback when the model returns all-zero weights."""
    weights = dict.fromkeys(SCORABLE_ATTRIBUTES, 0.0)
    for name, salience in priorities.items():
        key = _canonical_priority(name)
        level = _coerce_float(salience)
        if key is not None and level is not None and level > 0.0:
            weights[key] = max(weights[key], min(1.0, level))
    return weights


def recommend_node(state: ShoppingState) -> dict[str, Any]:
    """Weights (LLM) -> pure scorer ranking (D3: the model never orders products)."""
    _emit(("status", {"stage": "ranking"}))
    priorities = state.get("intent", {}).get("priorities") or {}
    context_names = [
        name
        for name, salience in priorities.items()
        if (level := _coerce_float(salience)) is not None and level > 0.5
    ]
    weights_model = call_structured(
        get_llm(),
        PreferenceWeights,
        _llm_messages(
            _WEIGHTS_SYSTEM_PROMPT,
            state.get("pending_user_text", ""),
            {"task": "weights", "priorities": context_names},
        ),
    )
    weights = weights_model.model_dump()
    if not any(value > 0.0 for value in weights.values()):
        weights = _fallback_weights(priorities)
    ranked = score_products(state.get("candidates", []), weights)
    return {"ranked": ranked, "weights": weights}


# ---------------------------------------------------------------------------
# ui_plan
# ---------------------------------------------------------------------------

_PLAN_ERROR_PAYLOAD: dict[str, str] = {
    "message": "The model produced an invalid UI plan.",
    "code": "structured_output",
}

#: Deterministic title of the normal-turn product grid. Plan selection is
#: code-owned (architecture-review fix): the former PlanSelection LLM call
#: returned this same string in every mode, so the title is now a constant —
#: normal turns make 3 model calls (intent, weights, narration), not 4.
PLAN_TITLE: str = "Best matches for your needs"


def _envelope(state: ShoppingState) -> dict[str, Any]:
    """Plan envelope fields shared by every assembly path (no wall clock)."""
    return {
        "plan_version": "1",
        "session_id": state.get("session_id") or "",
        "turn_id": state.get("turn_id", 0) + 1,
    }


def _rank_order_targets(state: ShoppingState, targets: tuple[str, ...]) -> list[str]:
    """Order comparison targets best-ranked first (ranked position, then the
    caller's order for products the current ranking does not contain)."""
    order = {pid: index for index, pid in enumerate(ranked_ids(state))}
    unranked = len(order)
    indexed = list(enumerate(targets))
    indexed.sort(key=lambda pair: (order.get(pair[1], unranked), pair[0]))
    return [pid for _index, pid in indexed]


def _cart_view_plan(state: ShoppingState, cart: list[dict[str, Any]]) -> UIPlan:
    """Deterministic ``cart_view`` plan: lines + catalog-priced total.

    Policy (mirrors the ``cart-one-item.json`` fixture): one
    ``remove_from_cart`` action per line while there are at most 3 lines,
    none beyond that.
    """
    summary = get_cart(cart, get_catalog())
    lines = list(summary.lines)
    actions = [
        UIAction(type="remove_from_cart", label="Remove", payload={"productId": line.product_id})
        for line in lines
    ]
    if len(lines) > 3:
        actions = []
    return UIPlan(
        **_envelope(state),
        root=ComponentNode(
            type="cart_view",
            props=CartViewProps(
                items=[
                    CartLine(product_id=line.product_id, quantity=line.quantity) for line in lines
                ],
                total_usd=summary.total_usd,
            ),
            actions=actions,
        ),
    )


def _comparison_value(product: Product, attribute: str) -> Any:
    """Display-ready value for one catalog attribute (``None`` → client renders
    a placeholder). Review attributes come from the pre-scored mirror (D5);
    everything else is a direct field."""
    if attribute in {"comfort", "anc", "sound", "battery", "value"}:
        return getattr(product.review_scores, attribute, None)
    if attribute == "codecs":
        return ", ".join(product.codecs) or None
    return getattr(product, attribute, None)


def _build_followup_plan(
    state: ShoppingState, followup: dict[str, Any]
) -> tuple[UIPlan, dict[str, Any]]:
    """Assemble a US4 follow-up plan deterministically — no model call is
    involved: the component kind was already fixed by
    :func:`app.graph.followups.resolve_followup`, so there is nothing left for
    a model to choose. Returns ``(plan, extra_state_update)`` where the extra
    covers ``selected_ids`` and cart mutations (performed via the pure tools
    in ``app.tools.cart``)."""
    kind = followup.get("kind")
    targets = tuple(pid for pid in (followup.get("product_ids") or []) if isinstance(pid, str))
    if kind == "disclosure":
        body = str(followup.get("disclosure") or NO_PRODUCTS_DISCLOSURE)
        return (
            UIPlan(
                **_envelope(state),
                root=ComponentNode(type="text_block", props=TextBlockProps(body=body)),
            ),
            {},
        )
    if kind == "compare":
        ordered = _rank_order_targets(state, targets)
        best = ordered[0]
        best_name = next(p.name for p in get_catalog() if p.id == best)
        catalog_by_id = {p.id: p for p in get_catalog()}
        values = {
            pid: {
                attr: _comparison_value(catalog_by_id[pid], attr) for attr in COMPARISON_ATTRIBUTES
            }
            for pid in ordered
        }
        plan = UIPlan(
            **_envelope(state),
            root=ComponentNode(
                type="comparison_table",
                props=ComparisonTableProps(
                    product_ids=ordered,
                    attributes=list(COMPARISON_ATTRIBUTES),
                    values=values,
                ),
                actions=[
                    UIAction(
                        type="choose",
                        label=f"Choose {best_name}",
                        payload={"productId": best},
                    )
                ],
            ),
        )
        return plan, {"selected_ids": ordered}
    if kind == "details":
        plan = UIPlan(
            **_envelope(state),
            root=ComponentNode(
                type="product_details",
                props=ProductDetailsProps(product_id=targets[0], show_quotes=True),
            ),
        )
        return plan, {"selected_ids": [targets[0]]}
    cart = list(state.get("cart") or [])
    extra: dict[str, Any] = {}
    if kind == "add_to_cart":
        cart = add_to_cart(cart, get_catalog(), targets[0])
        extra = {"cart": cart}
    elif kind == "remove_from_cart":
        cart = remove_from_cart(cart, get_catalog(), targets[0])
        extra = {"cart": cart}
    return _cart_view_plan(state, cart), extra


def ui_plan_node(state: ShoppingState) -> dict[str, Any]:
    """Assemble + validate the plan deterministically, then emit ``ui_update``.

    Normal turns: the plan is assembled entirely from ranked data — component
    kind and title are code policy (D3 in spirit: the model configures
    weights and narration, never plan structure). US4 follow-up turns:
    :func:`_build_followup_plan` assembles the matching component, also with
    no model call at all. A plan that fails Pydantic or catalog-aware
    validation is never emitted — the turn ends with one ``error`` frame
    instead (FR-008 / SC-004).
    """
    _emit(("status", {"stage": "building_ui"}))
    ranked = state.get("ranked", [])
    top = list(ranked[:TOP_N])
    top_ids = [scored.product_id for scored in top]
    followup = state.get("followup")
    try:
        if isinstance(followup, dict):
            plan, extra = _build_followup_plan(state, followup)
        else:
            # This wave renders a product grid for normal turns; follow-up
            # turns assemble the other registry types deterministically.
            plan = UIPlan(
                **_envelope(state),
                root=ComponentNode(
                    type="product_grid",
                    props=ProductGridProps(
                        title=PLAN_TITLE,
                        product_ids=top_ids,
                        ranked=True,
                    ),
                    actions=[
                        UIAction(type="compare", label="Compare"),
                        UIAction(type="details", label="Details"),
                        UIAction(type="add_to_cart", label="Add to cart"),
                    ],
                ),
            )
            extra = {"selected_ids": top_ids}
        validate_plan(plan, catalog_id_set())
    except (PlanValidationError, ValidationError):
        _emit(("error", dict(_PLAN_ERROR_PAYLOAD)))
        return {"error": dict(_PLAN_ERROR_PAYLOAD)}
    serialized = serialize_plan(plan)
    _emit(("ui_update", serialized))
    return {"plan": serialized, "turn_id": plan.turn_id, **extra}


# ---------------------------------------------------------------------------
# respond
# ---------------------------------------------------------------------------


def _clean_reason(product_name: str, reason: str) -> str:
    """Strip a mock-style leading ``"Name:"`` and guarantee sentence punctuation."""
    cleaned = reason.strip()
    prefix = f"{product_name}:"
    if cleaned.startswith(prefix):
        cleaned = cleaned[len(prefix) :].strip()
    return cleaned if cleaned.endswith(".") else f"{cleaned}."


def _assumption_note(assumptions: list[str]) -> str:
    """Deterministic ``"Note: ..."`` prefix disclosing recorded assumptions.

    Each assumption becomes a capitalized sentence (trailing period added when
    missing); the prefix is empty when there is nothing to disclose, so US1
    turns are byte-identical to before.
    """
    sentences: list[str] = []
    for item in assumptions:
        text = str(item).strip()
        if not text:
            continue
        text = text[0].upper() + text[1:]
        if not text.endswith((".", "!", "?")):
            text += "."
        sentences.append(text)
    if not sentences:
        return ""
    return f"Note: {' '.join(sentences)} "


def _name_list(names: list[str]) -> str:
    """Deterministic enumeration: "A and B" / "A, B and C"."""
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def _followup_narration(
    state: ShoppingState, followup: dict[str, Any], by_id: dict[str, Product]
) -> str:
    """Deterministic template narration for US4 follow-up turns — the
    Narration LLM call is skipped because the spoken line is fully determined
    by the resolved targets and catalog data (grounded names/prices, never
    model prose). Assumption notes are not prepended: follow-up commands
    introduce no new assumptions."""
    kind = followup.get("kind")
    names = [
        by_id[pid].name if pid in by_id else pid
        for pid in (followup.get("product_ids") or [])
        if isinstance(pid, str)
    ]
    if kind == "disclosure":
        return str(followup.get("disclosure") or NO_PRODUCTS_DISCLOSURE)
    if kind == "compare":
        return f"Here's the side-by-side comparison of {_name_list(names)}."
    if kind == "details":
        return f"Here's more about {names[0]}."
    if kind == "add_to_cart":
        return f"Added {names[0]} to your cart."
    if kind == "remove_from_cart":
        return f"Removed {names[0]} from your cart."
    # cart_view: lines with quantities plus the catalog-priced total.
    summary = get_cart(list(state.get("cart") or []), get_catalog())
    if not summary.lines:
        return "Your cart is empty."
    items = ", ".join(f"{by_id[line.product_id].name} x{line.quantity}" for line in summary.lines)
    return f"Your cart: {items} — total {_fmt_price(summary.total_usd)}."


def respond_node(state: ShoppingState) -> dict[str, Any]:
    """Grounded narration streamed as word-paired ``message_delta`` chunks.

    US4 follow-up turns use the deterministic templates of
    :func:`_followup_narration` instead of the Narration call. Normal turns:
    recorded assumptions (budget default, relaxed filters, contradictions)
    are disclosed first as a deterministic ``Note:`` prefix (US2: state the
    assumption / flag the trade-off). A failed turn (``state["error"]`` set
    by ``ui_plan``) ends quietly: the already-emitted ``error`` frame is
    terminal and no deltas follow it.
    """
    if state.get("error"):
        return {}
    followup = state.get("followup")
    by_id = {product.id: product for product in get_catalog()}
    if isinstance(followup, dict):
        text = _followup_narration(state, followup, by_id)
    else:
        ranked = state.get("ranked", [])
        top = list(ranked[:TOP_N])
        budget = _coerce_float((state.get("intent") or {}).get("budget_usd"))
        context_products = []
        for scored in top:
            product = by_id.get(scored.product_id)
            if product is None:
                continue
            context_products.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "highlights": _highlights(product, scored, budget),
                }
            )
        narration = call_structured(
            get_llm(),
            Narration,
            _llm_messages(
                _NARRATION_SYSTEM_PROMPT,
                state.get("pending_user_text", ""),
                {"task": "narration", "products": context_products},
            ),
        )
        valid_ids = {scored.product_id for scored in top}
        reasons = []
        for item in narration.per_product:
            # data-model.md: narrated ids are validated against the ranking;
            # invalid ones are dropped, never forwarded.
            if item.product_id not in valid_ids:
                continue
            product = by_id.get(item.product_id)
            if product is None:
                continue
            name = product.name
            reasons.append(
                f"{name} ({_fmt_price(product.price_usd)}): {_clean_reason(name, item.reason)}"
            )
        text = " ".join(
            part
            for part in (
                narration.intro.strip(),
                " ".join(reasons).strip(),
                narration.outro.strip(),
            )
            if part
        )
        assumptions = list((state.get("intent") or {}).get("assumptions") or [])
        text = _assumption_note(assumptions) + text
    for chunk in _chunk_words(text):
        _emit(("message_delta", {"text": chunk}))
    messages = [*state.get("messages", []), {"role": "assistant", "content": text}]
    return {"messages": messages}
