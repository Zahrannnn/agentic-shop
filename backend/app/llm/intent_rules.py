"""Pure regex rules for intent parsing — the shared judgment baseline.

Extracted from ``app.llm.client`` so the mock LLM handler and the mock Jev
judgment layer (``app.llm.jev``) derive their answers from ONE rule set: the
two mocks must agree exactly, and tests pin them against each other (D9).
Everything here is pure and deterministic — fixed-order pattern tables, no
clock, no randomness (constitution III).
"""

from __future__ import annotations

import re
from typing import Any

# Priority keyword patterns for intent extraction, checked in this fixed order
# (determinism, constitution III). Case-insensitive substrings/words.
PRIORITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"noise[ -]?cancell|\banc\b", "anc"),
    (r"comfort", "comfort"),
    (r"battery", "battery"),
    (r"sound", "sound"),
    (r"cheap|value", "value"),
)

#: Category patterns in fixed precedence order (determinism, constitution III):
#: the FIRST matching pattern wins, so a message that somehow names both
#: categories is classified as the earlier entry ("headphones"). "headphones"
#: never contains the earbud spellings and vice versa, so the order only
#: matters for pathological multi-category messages — documented here and
#: pinned by tests.
CATEGORY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"headphones?\b", "headphones"),
    (r"ear[\s-]?buds?\b", "earbuds"),
)

_USE_CASE_RE = re.compile(r"\bfor\s+([^\n]+)", re.IGNORECASE)
#: Use case runs until punctuation or a budget mention ("...for long flights
#: under $200" -> "long flights").
_USE_CASE_CUT_RE = re.compile(r"[.,;!?]|\bunder\b\s*\$?\s*\d|\$\s?\d")
BUDGET_RE = re.compile(r"\$\s?(\d[\d,]*)")


def extract_use_case(text: str) -> str | None:
    """Text after the first `` for ``, up to punctuation or a budget mention."""
    match = _USE_CASE_RE.search(text)
    if match is None:
        return None
    segment = match.group(1)
    cut = _USE_CASE_CUT_RE.search(segment)
    if cut is not None:
        segment = segment[: cut.start()]
    segment = segment.strip().strip("\"'").strip()
    return segment or None


def extract_budget_usd(text: str) -> int | None:
    """First ``$N[,N]`` amount in the text, as an int; ``None`` when absent."""
    match = BUDGET_RE.search(text)
    if match is None:
        return None
    return int(match.group(1).replace(",", ""))


def extract_category(text: str) -> str | None:
    """First catalog category whose pattern matches (lowercased text)."""
    lowered = text.lower()
    return next(
        (slug for pattern, slug in CATEGORY_PATTERNS if re.search(pattern, lowered)),
        None,
    )


def mentioned_priority_keys(text: str) -> list[str]:
    """Canonical priority keys mentioned in the text, in pattern-table order."""
    lowered = text.lower()
    keys: list[str] = []
    for pattern, key in PRIORITY_PATTERNS:
        if key not in keys and re.search(pattern, lowered):
            keys.append(key)
    return keys


def extract_intent_fields(text: str) -> dict[str, Any]:
    """The regex-baseline intent payload for one user message.

    Produces exactly what the LLM-mock ``IntentExtraction`` handler produced:
    budget (both ``budget`` and ``budget_usd`` spellings — field filtering
    keeps whichever the schema uses), category, priorities at salience 1.0
    for mentioned attributes, and the rule-parsed use case.
    """
    data: dict[str, Any] = {}
    budget = extract_budget_usd(text)
    if budget is not None:
        data["budget"] = budget
        data["budget_usd"] = budget
    data["category"] = extract_category(text)
    data["priorities"] = dict.fromkeys(mentioned_priority_keys(text), 1.0)
    data["use_case"] = extract_use_case(text)
    return data
