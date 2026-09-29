"""TypeSafe Jev judgment layer (DECISIONS.md D9) — the "System One" doorway.

Jev (TypeSafe AI's "System One" model) answers typed questions with calibrated
probabilities in ONE batched request — no text generation. Request shape
(docs.typeSafe.ai → /api): ``POST`` with ``{"state", "model", "questions"}``
where each question is a ``noul`` (yes/no), ``choice`` (pick one of up to 255
criteria-described options), or ``score`` (rubric rating); answers return as
probabilities plus a derived ``confidence``. This module is the ONLY place Jev
access is configured (constitution II), mirroring :mod:`app.llm.client`:

- ``JEV_MODE=off``  — disabled; the graph keeps the LLM intent path (default,
  so the shipped pipeline is byte-identical to pre-D9 behavior);
- ``JEV_MODE=mock`` — deterministic offline judgments (keyless CI). Answers
  derive from :mod:`app.llm.intent_rules`, so Jev-mock ≡ LLM-mock for intent;
- ``JEV_MODE=real`` — httpx against the API; fails fast without ``JEV_API_KEY``.

Resilience mirrors D8: transient failures (HTTP 429/529, network errors,
response-schema violations) are retried EXACTLY once, then :class:`JevError`
surfaces as one ``error`` SSE frame with code ``jev``.

Public surface
--------------
- ``get_jev()`` / ``reset_jev_cache()`` — cached factory + test hook.
- ``build_intent_questions(categories)`` — pure question map for intent.
- ``jev_ask_intent(message, categories)`` — one batched judgment returning
  :class:`JevIntentAnswers` (the judgment analog of ``IntentExtraction``;
  the graph maps it, keeping the llm→graph layering one-way).
- ``JevError`` — typed failure for the API layer.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.intent_rules import (
    extract_budget_usd,
    extract_category,
    mentioned_priority_keys,
)

__all__ = [
    "CATEGORY_CONFIDENCE_FLOOR",
    "HttpxJevClient",
    "JevError",
    "JevIntentAnswers",
    "JevResponse",
    "MockJevClient",
    "PRIORITY_KEYS",
    "UNCLEAR_CATEGORY",
    "build_intent_questions",
    "get_jev",
    "jev_ask_intent",
    "reset_jev_cache",
]


class JevError(RuntimeError):
    """Raised when a Jev judgment fails on both attempts (D9 / D8 spirit).

    Never raw API output, never a silent fallback — the API layer maps this to
    a single terminal ``error`` event with code ``jev``.
    """


# ---------------------------------------------------------------------------
# Question vocabulary (pure)
# ---------------------------------------------------------------------------

#: The five canonical scorable attributes, in PreferenceWeights declaration
#: order. Question ids are ``p_<key>``.
PRIORITY_KEYS: tuple[str, str, str, str, str] = ("anc", "comfort", "battery", "sound", "value")

#: Natural-language descriptions per priority key (what the shopper emphasizes).
_PRIORITY_DESCRIPTIONS: dict[str, str] = {
    "anc": "noise cancellation, quietness, isolation from plane or office noise",
    "comfort": "wearing comfort for long sessions, light fit, no clamping",
    "battery": "battery life, how long the product runs per charge",
    "sound": "sound quality, audio fidelity",
    "value": "value for money, being cheap or a good deal",
}

#: Ordered score rubric levels (2–10 allowed by the API; 4 keeps the mapping
#: to salience crisp: level index / 3 → [0, 1]).
PRIORITY_RUBRIC: tuple[str, str, str, str] = (
    "unmentioned",
    "mentioned",
    "important",
    "critical",
)

#: Choice option returned when no category is stated / the message is ambiguous.
UNCLEAR_CATEGORY: str = "unclear"

#: Static criteria descriptions for known catalog categories; anything else
#: gets a generic description (future categories need no code change).
_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "headphones": "over-ear or on-ear headphones",
    "earbuds": "in-ear earbuds",
}


def build_intent_questions(categories: Sequence[str]) -> dict[str, Any]:
    """Build the batched intent question map (pure; D9).

    One ``choice`` over the catalog categories plus ``unclear``, and one
    ``score`` rubric per scorable attribute — everything downstream consumes
    of ``IntentExtraction`` except free text, which Jev deliberately does not
    generate (``use_case`` has no downstream consumers; budget comes from the
    deterministic dollar regex, not the model).
    """
    criteria: dict[str, str] = {
        category: _CATEGORY_DESCRIPTIONS.get(category, f"products in the {category} category")
        for category in sorted(categories)
    }
    criteria[UNCLEAR_CATEGORY] = "no category stated, or the request is ambiguous"
    questions: dict[str, Any] = {
        "category": {
            "type": "choice",
            "instructions": ("Which product category does the shopper ask for in `message`?"),
            "criteria": criteria,
        }
    }
    for key in PRIORITY_KEYS:
        questions[f"p_{key}"] = {
            "type": "score",
            "instructions": (f"How much does the shopper emphasize {_PRIORITY_DESCRIPTIONS[key]}?"),
            "criteria": list(PRIORITY_RUBRIC),
        }
    return questions


# ---------------------------------------------------------------------------
# Wire models (mirror the documented response schema)
# ---------------------------------------------------------------------------


class NoulAnswer(BaseModel):
    """Yes/no answer: probability of "yes" in [0, 1]."""

    model_config = ConfigDict(extra="ignore")

    noul: float = Field(ge=0.0, le=1.0)


class ChoiceAnswer(BaseModel):
    """Pick-one answer: top option, full distribution, derived confidence."""

    model_config = ConfigDict(extra="ignore")

    choice: str = Field(min_length=1)
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)


class ScoreAnswer(BaseModel):
    """Rubric answer: probability-weighted level (may land between levels)."""

    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0.0)
    legend: dict[str, str] = Field(default_factory=dict)
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)


class JevResponse(BaseModel):
    """One judgment response: answers keyed by the question ids we chose."""

    model_config = ConfigDict(extra="ignore")

    model: str = Field(min_length=1)
    answers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class JevClient(Protocol):
    """Consumer surface: one batched judgment request."""

    def ask(self, state: Mapping[str, Any], questions: Mapping[str, Any]) -> JevResponse: ...


class MockJevClient:
    """Deterministic offline Jev for keyless CI (research R5, D9).

    Answers are derived from :mod:`app.llm.intent_rules` — the SAME regex
    baseline the LLM-mock intent handler uses — so ``JEV_MODE=mock`` and the
    LLM mock path produce equivalent intent for the same message:

    - the ``choice`` question picks the regex-detected category (confidence
      0.9) or ``unclear`` (confidence 1.0);
    - each ``p_<key>`` score lands on ``critical`` when the baseline mentions
      the attribute (salience 1.0, matching the LLM mock) and on
      ``unmentioned`` otherwise;
    - other question types get a neutral ``noul`` of 0.0.
    """

    def ask(self, state: Mapping[str, Any], questions: Mapping[str, Any]) -> JevResponse:
        message = str(state.get("message", ""))
        category = extract_category(message)
        mentioned = set(mentioned_priority_keys(message))
        answers: dict[str, dict[str, Any]] = {}
        for question_id, question in questions.items():
            question_type = question.get("type")
            if question_type == "choice":
                if category is not None and category in question.get("criteria", {}):
                    answers[question_id] = {
                        "choice": category,
                        "probabilities": {category: 0.9, UNCLEAR_CATEGORY: 0.1},
                        "confidence": 0.9,
                    }
                else:
                    answers[question_id] = {
                        "choice": UNCLEAR_CATEGORY,
                        "probabilities": {UNCLEAR_CATEGORY: 1.0},
                        "confidence": 1.0,
                    }
            elif question_type == "score":
                key = question_id.removeprefix("p_")
                level = 3.0 if key in mentioned else 0.0
                top = str(int(level))
                answers[question_id] = {
                    "score": level,
                    "legend": {str(index): name for index, name in enumerate(PRIORITY_RUBRIC)},
                    "probabilities": {top: 1.0},
                    "confidence": 1.0,
                }
            else:
                answers[question_id] = {"noul": 0.0}
        return JevResponse(model="jev-mock", answers=answers)


#: HTTP statuses worth one retry (TypeSafe docs: 429 rate limit, 529 overloaded).
_RETRY_STATUS_CODES: frozenset[int] = frozenset({429, 529})

#: Fixed (no jitter) delay before the single retry — real mode only; mock mode
#: never sleeps. Module constant so tests can pin it.
RETRY_DELAY_SECONDS: float = 0.5


class HttpxJevClient:
    """Real-mode Jev client over httpx against ``JEV_BASE_URL``.

    Retries exactly once on transient failure (429/529, transport errors,
    response-schema violations), then raises :class:`JevError`. ``transport``
    exists for tests (``httpx.MockTransport``); production leaves it ``None``.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "jev-latest",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def ask(self, state: Mapping[str, Any], questions: Mapping[str, Any]) -> JevResponse:
        payload = {
            "state": dict(state),
            "model": self._model,
            "questions": dict(questions),
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last_failure = "no attempt made"
        for _attempt in range(2):
            try:
                response = self._client.post(self._base_url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_failure = f"transport error: {exc}"
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            if response.status_code in _RETRY_STATUS_CODES:
                last_failure = f"HTTP {response.status_code}"
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            if response.status_code >= 400:
                # 401/422/… are request-side problems — retrying the identical
                # request cannot fix them, so fail immediately.
                raise JevError(f"jev rejected the request (HTTP {response.status_code})")
            try:
                return JevResponse.model_validate(response.json())
            except ValidationError as exc:
                last_failure = f"response failed schema validation: {exc.errors()[0]}"
                continue
        raise JevError(f"jev judgment failed twice ({last_failure})")


# ---------------------------------------------------------------------------
# Factory (constitution II — the only place Jev access is configured)
# ---------------------------------------------------------------------------


def _build_jev(settings: Any) -> JevClient:
    """Construct (uncached) the Jev client described by *settings*.

    ``JEV_MODE=real`` fails fast without ``JEV_API_KEY`` — it must never
    silently degrade to the mock and mask a misconfiguration (same spirit as
    ``_build_llm``). ``off``/``mock`` both yield the offline client; ``off``
    simply never triggers a Jev call.
    """
    mode = str(settings.JEV_MODE or "off").strip().lower()
    if mode != "real":
        return MockJevClient()
    if not settings.JEV_API_KEY:
        raise RuntimeError(
            "JEV_MODE=real requires JEV_API_KEY to be set in the environment. "
            "Credentials are env-only (constitution II); no keys may be "
            "hard-coded. Use JEV_MODE=mock for keyless offline runs."
        )
    return HttpxJevClient(
        base_url=settings.JEV_BASE_URL,
        api_key=settings.JEV_API_KEY,
        model=settings.JEV_MODEL,
    )


_jev_cache_key: tuple[str, str, str, str] | None = None
_cached_jev: JevClient | None = None


def get_jev() -> JevClient:
    """Return the cached Jev client for the current settings (mirrors
    :func:`app.llm.client.get_llm`; call :func:`reset_jev_cache` in tests
    after changing the environment)."""
    global _jev_cache_key, _cached_jev
    from app.config import get_settings  # noqa: PLC0415 — lazy by design

    settings = get_settings()
    key = (
        str(settings.JEV_MODE or "off"),
        str(settings.JEV_MODEL or ""),
        str(settings.JEV_BASE_URL or ""),
        str(settings.JEV_API_KEY or ""),
    )
    if _cached_jev is None or key != _jev_cache_key:
        _cached_jev = _build_jev(settings)
        _jev_cache_key = key
    return _cached_jev


def reset_jev_cache() -> None:
    """Drop the cached Jev client (test hook after env changes)."""
    global _jev_cache_key, _cached_jev
    _jev_cache_key = None
    _cached_jev = None


# ---------------------------------------------------------------------------
# Intent judgment (the graph-facing consumer)
# ---------------------------------------------------------------------------

#: A category choice below this confidence is treated as ``unclear`` and the
#: deterministic clarify gate asks instead. One reviewable constant (D9), pinned
#: by tests; raising it trades false categories for more clarify questions.
CATEGORY_CONFIDENCE_FLOOR: float = 0.5

_SALIENCE_SCALE: float = float(len(PRIORITY_RUBRIC) - 1)


class JevIntentAnswers(BaseModel):
    """The judgment analog of ``IntentExtraction``: judgment output only.

    ``use_case`` is deliberately absent — Jev produces typed decisions, not
    free text, and no downstream node consumes the use case.
    """

    model_config = ConfigDict(extra="ignore")

    category: str | None = None
    budget_usd: float | None = None
    priorities: dict[str, float] = Field(default_factory=dict)


def _as_float(value: Any) -> float | None:
    """Best-effort ``float`` coercion; ``None`` for anything non-numeric."""
    try:
        coerced = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return coerced


def jev_ask_intent(message: str, categories: Sequence[str]) -> JevIntentAnswers:
    """Run ONE batched Jev judgment for the intent fields (D9).

    Mapping rules (pure, deterministic given the response):

    - ``category``: the choice wins when it names a catalog category AND its
      confidence clears :data:`CATEGORY_CONFIDENCE_FLOOR`; ``unclear`` or a
      low-confidence pick leaves it ``None`` (the clarify gate asks);
    - ``priorities``: each rubric ``score`` maps to salience
      ``score / (levels - 1)`` clamped to [0, 1]; zero-salience keys are
      omitted (identical semantics to the LLM path's merge);
    - ``budget_usd``: the deterministic dollar regex over the message —
      numeric extraction is code's job, never the model's.
    """
    questions = build_intent_questions(categories)
    response = get_jev().ask({"message": message}, questions)

    category: str | None = None
    raw_choice = response.answers.get("category")
    if raw_choice is not None:
        try:
            answer = ChoiceAnswer.model_validate(raw_choice)
        except ValidationError as exc:
            raise JevError(f"jev answer for 'category' is malformed: {exc.errors()[0]}") from exc
        confidence = _as_float(answer.confidence) or 0.0
        if (
            answer.choice in categories
            and answer.choice != UNCLEAR_CATEGORY
            and confidence >= CATEGORY_CONFIDENCE_FLOOR
        ):
            category = answer.choice

    priorities: dict[str, float] = {}
    for key in PRIORITY_KEYS:
        raw_score = response.answers.get(f"p_{key}")
        if raw_score is None:
            continue
        try:
            answer = ScoreAnswer.model_validate(raw_score)
        except ValidationError as exc:
            raise JevError(f"jev answer for 'p_{key}' is malformed: {exc.errors()[0]}") from exc
        score = _as_float(answer.score)
        if score is None:
            continue
        salience = min(1.0, max(0.0, score / _SALIENCE_SCALE))
        if salience > 0.0:
            priorities[key] = salience

    budget = extract_budget_usd(message)
    return JevIntentAnswers(
        category=category,
        budget_usd=float(budget) if budget is not None else None,
        priorities=priorities,
    )
