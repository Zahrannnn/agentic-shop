"""LLM access layer — the single configured doorway to any model.

Constitution II: model name, base URL, and API key come exclusively from the
environment (``LLM_MODE``, ``LLM_MODEL``, ``OPENCODE_BASE_URL``,
``OPENCODE_API_KEY``); hard-coding any of them here is forbidden. Mock mode
(``LLM_MODE=mock``, the default) lets the whole pipeline run keyless and
offline (research R5) with fully deterministic outputs.

Public surface
--------------
- ``get_llm()`` — factory returning the cached ``ChatOpenAI`` (real mode) or
  ``MockChatLLM`` (mock mode / anything not explicitly ``real``).
- ``MockChatLLM`` — deterministic offline stand-in implementing the same
  consumer surface (``invoke`` + ``with_structured_output``) with per-schema
  canned handlers and test knobs (constructor ``behaviors`` and module-level
  ``register_mock_handler`` overrides for fault injection).
- ``call_structured(llm, schema, messages)`` — the D8/principle-IV resilience
  wrapper: Pydantic-validate every structured output, retry exactly once
  feeding the validation error back, then raise ``StructuredOutputError``.
- ``StructuredOutputError`` — typed failure surfaced to the graph, which maps
  it to a single ``error`` protocol event (never raw model output).
- ``register_mock_handler(name, fn)`` / ``reset_llm_cache()`` — test hooks.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

__all__ = [
    "MockChatLLM",
    "StructuredOutputError",
    "call_structured",
    "get_llm",
    "register_mock_handler",
    "reset_llm_cache",
]

#: A mock handler receives the full conversation text and the parsed context
#: dict extracted from the last ``<<<CONTEXT>>{...}<<<END_CONTEXT>>>`` block,
#: and returns a plain dict (filtered to the schema's fields for defaults).
MockHandler = Callable[[str, dict[str, Any]], dict[str, Any]]

#: Sentinel markers wrapping the machine-readable context block inside a message.
CONTEXT_OPEN = "<<<CONTEXT>>>"
CONTEXT_CLOSE = "<<<END_CONTEXT>>>"

#: Canonical scorable attribute keys, in data-model.md declaration order.
_WEIGHT_KEYS: tuple[str, str, str, str, str] = ("battery", "comfort", "anc", "sound", "value")

#: Salience-to-weight scale by number of mentioned priorities (task spec):
#: one -> 1.0; two -> 1.0/0.8; three -> 1.0/0.7/0.5; beyond three the last
#: factor repeats so behaviour stays total and deterministic.
_WEIGHT_SCALES: dict[int, tuple[float, ...]] = {1: (1.0,), 2: (1.0, 0.8)}

# Priority keyword patterns for intent extraction, checked in this fixed order
# (determinism, constitution III). Case-insensitive substrings/words.
_INTENT_PRIORITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"noise[ -]?cancell|\banc\b", "anc"),
    (r"comfort", "comfort"),
    (r"battery", "battery"),
    (r"sound", "sound"),
    (r"cheap|value", "value"),
)

#: Aliases used to normalise arbitrary priority names (from the context block)
#: onto canonical weight keys. First matching alias wins.
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

_USE_CASE_RE = re.compile(r"\bfor\s+([^\n]+)", re.IGNORECASE)
#: Use case runs until punctuation or a budget mention ("...for long flights
#: under $200" -> "long flights").
_USE_CASE_CUT_RE = re.compile(r"[.,;!?]|\bunder\b\s*\$?\s*\d|\$\s?\d")
_BUDGET_RE = re.compile(r"\$\s?(\d[\d,]*)")
_CATEGORY_HEADPHONE_RE = re.compile(r"headphones?\b")


class StructuredOutputError(RuntimeError):
    """Raised when a structured LLM output fails validation on both attempts.

    Principle IV / D8: retry exactly once with the validation error fed back,
    then surface a clean typed error — never raw model output, never a silent
    fallback.
    """


# ---------------------------------------------------------------------------
# Message / context extraction helpers
# ---------------------------------------------------------------------------


def _message_text(message: Any) -> str:
    """Return the text content of a LangChain message (or bare string)."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, Mapping):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return str(content)


def _parse_context_block(text: str) -> dict[str, Any]:
    """Leniently parse the last ``<<<CONTEXT>>>{...}<<<END_CONTEXT>>>`` block.

    Returns an empty dict when the block is absent or its JSON is malformed —
    parsing must never raise; the mock degrades to defaults deterministically.
    """
    start = text.rfind(CONTEXT_OPEN)
    if start == -1:
        return {}
    start += len(CONTEXT_OPEN)
    end = text.find(CONTEXT_CLOSE, start)
    if end == -1:
        return {}
    raw = text[start:end].strip()
    if not raw.startswith("{"):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_messages_payload(
    messages: Sequence[BaseMessage] | str,
) -> tuple[str, dict[str, Any]]:
    """Extract ``(full_conversation_text, context_dict)`` from messages.

    The context comes from the LAST message containing a sentinel block (and
    the last block within that message); absent or malformed -> ``{}``.
    """
    texts = [messages] if isinstance(messages, str) else [_message_text(m) for m in messages]
    conversation = "\n".join(texts)
    context: dict[str, Any] = {}
    for text in reversed(texts):
        if CONTEXT_OPEN in text:
            context = _parse_context_block(text)
            break
    return conversation, context


def _as_message_list(messages: Sequence[BaseMessage] | str) -> list[Any]:
    """Normalise a bare string prompt into a one-message list."""
    if isinstance(messages, str):
        return [HumanMessage(content=messages)]
    return list(messages)


def _filter_to_fields(schema: type[BaseModel], data: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only keys that exist on the schema, in schema declaration order."""
    return {key: data[key] for key in schema.model_fields if key in data}


# ---------------------------------------------------------------------------
# Default deterministic mock handlers
# ---------------------------------------------------------------------------


def _weight_scale(count: int) -> tuple[float, ...]:
    """Deterministic descending weight factors for ``count`` priorities."""
    if count in _WEIGHT_SCALES:
        return _WEIGHT_SCALES[count]
    if count >= 3:
        return (1.0, 0.7, 0.5) + (0.5,) * (count - 3)
    return ()


def _priority_names(raw: Any) -> list[str]:
    """Normalise context priorities (list of names, dicts, or dict keys)."""
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        return [str(key) for key in raw]
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, Sequence):
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, Mapping):
                name = item.get("name") or item.get("attribute") or item.get("key")
                if name:
                    names.append(str(name))
        return names
    return []


def _canonical_priority_key(name: str) -> str | None:
    """Map an arbitrary priority name onto a canonical weight key (or None)."""
    lowered = name.lower().strip()
    for needle, key in _PRIORITY_ALIASES:
        if needle in lowered:
            return key
    return None


def _extract_use_case(text: str) -> str | None:
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


def _intent_extraction_handler(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Regex-based deterministic intent extraction over the user text."""
    _ = context  # intent comes from the user text only
    lowered = text.lower()
    data: dict[str, Any] = {}
    budget_match = _BUDGET_RE.search(text)
    if budget_match is not None:
        budget = int(budget_match.group(1).replace(",", ""))
        # Emit both spellings; field filtering keeps whichever the schema uses.
        data["budget"] = budget
        data["budget_usd"] = budget
    data["category"] = "headphones" if _CATEGORY_HEADPHONE_RE.search(lowered) else None
    priorities: dict[str, float] = {}
    for pattern, key in _INTENT_PRIORITY_PATTERNS:
        if key not in priorities and re.search(pattern, lowered):
            priorities[key] = 1.0
    data["priorities"] = priorities
    data["use_case"] = _extract_use_case(text)
    return data


def _preference_weights_handler(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Map context priorities onto weights; balanced 0.2 when none mentioned."""
    _ = text  # weights come from the context block only
    keys: list[str] = []
    for name in _priority_names(context.get("priorities")):
        key = _canonical_priority_key(name)
        if key is not None and key not in keys:
            keys.append(key)
    weights = dict.fromkeys(_WEIGHT_KEYS, 0.0)
    if keys:
        for key, factor in zip(keys, _weight_scale(len(keys)), strict=True):
            weights[key] = factor
    else:
        weights = dict.fromkeys(_WEIGHT_KEYS, 0.2)
    return {key: weights[key] for key in _WEIGHT_KEYS}


def _narration_handler(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Deterministic narration from context products, with generic fallbacks."""
    _ = text  # narration is grounded in the context block only
    products = context.get("products") or []
    per_product: list[dict[str, Any]] = []
    for product in products:
        if not isinstance(product, Mapping):
            continue
        product_id = product.get("id") or product.get("product_id")
        name = product.get("name") or (str(product_id) if product_id else "this product")
        highlights = product.get("highlights") or []
        highlight = ""
        if isinstance(highlights, Sequence) and not isinstance(highlights, str) and highlights:
            highlight = str(highlights[0]).strip().rstrip(".")
        highlight = highlight or "a strong match for your priorities"
        per_product.append({"product_id": product_id, "reason": f"{name}: {highlight}."})
    intro = (
        "Based on your priorities, here are my top picks."
        if per_product
        else "Here are some options for you."
    )
    return {
        "intro": intro,
        "per_product": per_product,
        "outro": "Want me to compare any of these?",
    }


def _plan_selection_handler(text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Component choice from context, defaulting to a product grid."""
    _ = text  # plan selection is driven by the context block only
    data: dict[str, Any] = {
        "component": context.get("suggested_component") or "product_grid",
        "title": context.get("title") or "Best matches",
    }
    if "product_ids" in context:
        data["product_ids"] = list(context["product_ids"])
    return data


_DEFAULT_HANDLERS: dict[str, MockHandler] = {
    "IntentExtraction": _intent_extraction_handler,
    "PreferenceWeights": _preference_weights_handler,
    "Narration": _narration_handler,
    "PlanSelection": _plan_selection_handler,
}

#: Module-level per-schema handler overrides (first consulted after the
#: instance's own ``behaviors``). Mutated only via ``register_mock_handler``.
_MOCK_HANDLER_OVERRIDES: dict[str, MockHandler] = {}


def register_mock_handler(name: str, handler: MockHandler) -> None:
    """Register (or replace) the mock handler for a schema class *name*.

    Precedence in :meth:`MockChatLLM.with_structured_output`: instance
    ``behaviors`` -> registered overrides -> built-in default handlers.
    Intended for tests (e.g. fault injection: always-invalid output).
    """
    _MOCK_HANDLER_OVERRIDES[name] = handler


# ---------------------------------------------------------------------------
# Mock chat model
# ---------------------------------------------------------------------------


class _StructuredMock:
    """Callable returned by :meth:`MockChatLLM.with_structured_output`.

    Mirrors the runnable surface of the real ``ChatOpenAI.with_structured_output``
    result: callers use ``structured.invoke(messages)``.
    """

    def __init__(self, schema: type[BaseModel], llm: MockChatLLM) -> None:
        self._schema = schema
        self._llm = llm

    def invoke(self, messages: Sequence[BaseMessage] | str) -> Any:
        """Produce deterministic data for the bound schema (instance or dict)."""
        text, context = _extract_messages_payload(messages)
        schema = self._schema
        name = schema.__name__
        override = self._llm._behaviors.get(name) or _MOCK_HANDLER_OVERRIDES.get(name)
        if override is not None:
            return override(text, context)
        default = _DEFAULT_HANDLERS.get(name)
        if default is None:
            # Unknown schema without a scripted handler: neutral empty payload;
            # validation downstream decides if that is fatal.
            return {}
        return _filter_to_fields(schema, default(text, context))


class MockChatLLM:
    """Deterministic offline stand-in for ``ChatOpenAI`` (research R5).

    Implements the same consumer surface the factory's callers use —
    ``invoke`` plus ``with_structured_output`` — returning canned outputs
    keyed by the requested Pydantic model class name. All behaviour is pure
    and deterministic: identical input yields identical output (principle III).

    ``behaviors`` maps a schema class NAME to a handler
    ``(messages_text, context) -> dict`` so tests can script outputs (e.g.
    always-invalid payloads for fault injection, SC-007).
    """

    def __init__(self, behaviors: Mapping[str, MockHandler] | None = None) -> None:
        self._behaviors: dict[str, MockHandler] = dict(behaviors) if behaviors else {}

    def invoke(self, messages: Sequence[BaseMessage] | str) -> str:
        """Return a simple deterministic response for non-structured calls."""
        _ = messages
        return "mock response"

    def with_structured_output(self, schema: type[BaseModel]) -> _StructuredMock:
        """Return a structured callable bound to *schema*.

        Resolution order: instance ``behaviors`` -> module-level registered
        overrides -> built-in deterministic default handlers. Default-handler
        dicts are filtered to ``schema.model_fields`` keys; override handlers
        pass through unfiltered so fault-injection tests can produce invalid
        payloads that :func:`call_structured` must catch.

        ``invoke`` returns a schema instance or dict (validation is the
        caller's safety net per principle IV — the mock intentionally may
        return plain dicts).
        """
        return _StructuredMock(schema, self)


# ---------------------------------------------------------------------------
# Structured-output resilience wrapper (principle IV / D8)
# ---------------------------------------------------------------------------


def call_structured[ModelT: BaseModel](
    llm: Any,
    schema: type[ModelT],
    messages: Sequence[BaseMessage] | str,
) -> ModelT:
    """Invoke *llm* for *schema* with validate -> retry once -> fail clean.

    Native ``with_structured_output`` is tried first. Some gateway models only
    expose the Responses API or reject strict JSON schemas; when the native
    call fails at request time the model is remembered in
    :data:`_JSON_MODE_MODELS` and subsequent calls use schema-in-prompt JSON
    mode (:func:`_call_structured_json`) instead. Either way, outputs are
    Pydantic-validated (the safety net), a failed validation is retried
    EXACTLY once with the validation error fed back, and a second failure
    raises :class:`StructuredOutputError` for the graph to map to one
    ``error`` event.
    """
    base_messages = _as_message_list(messages)
    model_key = str(getattr(llm, "model_name", "") or id(llm))
    if model_key in _JSON_MODE_MODELS:
        return _call_structured_json(llm, schema, base_messages)
    structured = llm.with_structured_output(schema)
    try:
        result = structured.invoke(base_messages)
    except Exception:  # noqa: BLE001 — any request-time failure -> JSON mode
        _JSON_MODE_MODELS.add(model_key)
        return _call_structured_json(llm, schema, base_messages)
    try:
        return schema.model_validate(result)
    except ValidationError as first_error:
        retry_messages = [
            *base_messages,
            HumanMessage(
                content=(
                    f"Your previous response failed validation: {first_error}. "
                    "Respond again conforming to the schema."
                )
            ),
        ]
        try:
            retried = structured.invoke(retry_messages)
            return schema.model_validate(retried)
        except ValidationError as second_error:
            raise StructuredOutputError(str(second_error)) from second_error


def _result_text(result: Any) -> str:
    """Extract assistant text from an LLM response (message or bare string)."""
    text = getattr(result, "text", None)
    if isinstance(text, str) and text:
        return text
    return _message_text(result)


def _extract_json_object(text: str) -> Any:
    """Parse the first JSON object embedded in *text* (lenient about fences).

    Raises ``ValueError`` (``json.JSONDecodeError``) when no object is found —
    the caller treats that exactly like a validation failure.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("no JSON object found in model response")
    return json.loads(match.group(0))


def _call_structured_json[ModelT: BaseModel](
    llm: Any,
    schema: type[ModelT],
    base_messages: list[Any],
) -> ModelT:
    """Schema-in-prompt JSON mode for models without native structured output.

    The JSON schema travels in the prompt; the reply is extracted, parsed, and
    Pydantic-validated. Same retry semantics as the native path: exactly one
    retry with the validation error fed back, then
    :class:`StructuredOutputError`.
    """
    instruction = SystemMessage(
        content=(
            "Respond with ONLY a JSON object that conforms to the following "
            "JSON schema. No markdown fences, no commentary, no extra text:\n"
            + json.dumps(schema.model_json_schema())
        )
    )
    messages: list[Any] = [*base_messages, instruction]
    last_error: ValueError | None = None
    for _attempt in range(2):
        try:
            data = _extract_json_object(_result_text(llm.invoke(messages)))
            return schema.model_validate(data)
        except ValueError as error:  # JSONDecodeError and ValidationError
            last_error = error
            messages = [
                *base_messages,
                instruction,
                HumanMessage(
                    content=(
                        f"Your previous response failed validation: {error}. "
                        "Respond again with ONLY a JSON object conforming to "
                        "the schema."
                    )
                ),
            ]
    raise StructuredOutputError(str(last_error))


#: Models that failed their native structured-output contract at request time
#: (e.g. Responses-only gateway models). Cleared by :func:`reset_llm_cache`.
_JSON_MODE_MODELS: set[str] = set()


# ---------------------------------------------------------------------------
# Factory (constitution II) — the only place model access is configured
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BootstrapSettings:
    """Environment-read fallback used only while ``app.config`` is absent.

    Mirrors the agreed ``Settings`` field names (task T004). Once
    ``app.config.get_settings`` is importable it is always preferred; this
    keeps the LLM module runnable (and the keyless verification green) in the
    interim without touching any other module.
    """

    LLM_MODE: str = "mock"
    LLM_MODEL: str = ""
    OPENCODE_BASE_URL: str = ""
    OPENCODE_API_KEY: str = ""
    LLM_API_STYLE: str = "auto"

    @classmethod
    def from_env(cls) -> _BootstrapSettings:
        """Read the settings straight from process environment."""
        return cls(
            LLM_MODE=os.environ.get("LLM_MODE", "mock"),
            LLM_MODEL=os.environ.get("LLM_MODEL", ""),
            OPENCODE_BASE_URL=os.environ.get("OPENCODE_BASE_URL", ""),
            OPENCODE_API_KEY=os.environ.get("OPENCODE_API_KEY", ""),
            LLM_API_STYLE=os.environ.get("LLM_API_STYLE", "auto"),
        )


def _load_settings() -> Any:
    """Load settings lazily from ``app.config``, falling back to env vars."""
    try:
        from app.config import get_settings  # noqa: PLC0415 — lazy by design
    except ImportError:
        return _BootstrapSettings.from_env()
    return get_settings()


def _build_llm(settings: Any) -> Any:
    """Construct (uncached) the LLM described by *settings*.

    ``LLM_MODE=real`` fails fast with a clear ``RuntimeError`` when the model
    or API key is unset (research R8) — it must never silently degrade to the
    mock and mask a misconfiguration mid-conversation. Any other mode
    (including unset, i.e. ``mock`` by default) yields :class:`MockChatLLM`.
    """
    mode = str(settings.LLM_MODE or "mock").strip().lower()
    if mode != "real":
        return MockChatLLM()
    missing = [
        name
        for name, value in (
            ("LLM_MODEL", settings.LLM_MODEL),
            ("OPENCODE_API_KEY", settings.OPENCODE_API_KEY),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "LLM_MODE=real requires "
            + ", ".join(missing)
            + " to be set in the environment. Model, base URL, and API key are "
            "env-only (constitution II); no credentials may be hard-coded."
        )
    from langchain_openai import ChatOpenAI  # noqa: PLC0415 — lazy, mock stays light

    # LLM_API_STYLE=responses selects gateway models that only expose the
    # OpenAI Responses API (e.g. muse-spark on OpenCode Zen). Passing the
    # responses-only "truncation" key makes langchain route requests to
    # /responses instead of /chat/completions; it is a valid no-op there.
    api_style = str(settings.LLM_API_STYLE or "").strip().lower()
    model_kwargs = {"truncation": "disabled"} if api_style == "responses" else None
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.OPENCODE_API_KEY,
        base_url=settings.OPENCODE_BASE_URL or None,
        temperature=0,  # literal 0 — determinism, constitution III
        timeout=120,
        model_kwargs=model_kwargs,
    )


_llm_cache_key: tuple[str, str, str, str, str] | None = None
_cached_llm: Any | None = None


def get_llm() -> Any:
    """Return the cached LLM instance for the current settings.

    Mock mode (default) needs no key; real mode wires ``ChatOpenAI`` to the
    OpenCode gateway strictly via environment configuration. The instance is
    cached per settings tuple; call :func:`reset_llm_cache` in tests after
    changing the environment.
    """
    global _llm_cache_key, _cached_llm
    settings = _load_settings()
    key = (
        str(settings.LLM_MODE or "mock"),
        str(settings.LLM_MODEL or ""),
        str(settings.OPENCODE_BASE_URL or ""),
        str(settings.OPENCODE_API_KEY or ""),
        str(getattr(settings, "LLM_API_STYLE", "auto") or "auto"),
    )
    if _cached_llm is None or key != _llm_cache_key:
        _cached_llm = _build_llm(settings)
        _llm_cache_key = key
        _JSON_MODE_MODELS.clear()
    return _cached_llm


def reset_llm_cache() -> None:
    """Drop the cached LLM instance (test hook after env changes)."""
    global _llm_cache_key, _cached_llm
    _llm_cache_key = None
    _cached_llm = None
    _JSON_MODE_MODELS.clear()
