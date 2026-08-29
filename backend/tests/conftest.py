"""Shared pytest fixtures and fakes for the backend suite.

Nothing from the ``app`` package is imported at module level — modules such
as ``app.main`` and ``app.llm.client`` are produced by concurrent work waves,
so every ``app`` import happens lazily inside a fixture/helper body. This
keeps ``pytest --collect-only`` green at every stage of integration.

Helpers are importable from tests as::

    from tests.conftest import collect_sse
"""

import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

type ScriptedEntry = dict[str, Any] | Callable[[str, str], Any]
"""One :class:`ScriptedFakeLLM` script entry (see the class docstring)."""

type FakeLLMFactory = Callable[[list[ScriptedEntry]], ScriptedFakeLLM]
"""Signature of the callable produced by the ``fake_llm_factory`` fixture."""

_CONTEXT_BLOCK_RE = re.compile(r"<<<CONTEXT>>>(.*?)<<<END_CONTEXT>>>", re.DOTALL)


def _messages_text(messages: Any) -> str:
    """Flatten LangChain messages / strings / content blocks into plain text."""
    if isinstance(messages, str):
        return messages
    if isinstance(messages, dict):
        text = messages.get("text")  # LangChain content block: {"type": "text", ...}
        if isinstance(text, str):
            return text
        content = messages.get("content")
        return content if isinstance(content, str) else str(content)
    if isinstance(messages, (list, tuple)):
        return "\n".join(filter(None, (_messages_text(item) for item in messages)))
    content = getattr(messages, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        return "\n".join(filter(None, (_messages_text(block) for block in content)))
    if content is not None:
        return str(content)
    return str(messages)


def _extract_context(messages_text: str) -> str:
    """Return the prompt's ``<<<CONTEXT>>>...<<<END_CONTEXT>>>`` block, or ``""``.

    Mirrors the context-block parsing MockChatLLM applies, so scripted
    callable entries receive the same ``(messages_text, context)`` inputs.
    """
    match = _CONTEXT_BLOCK_RE.search(messages_text)
    return match.group(1).strip() if match else ""


class ScriptedFakeLLM:
    """Deterministic fake LLM replaying a scripted sequence of structured outputs.

    Same minimal surface as ``MockChatLLM`` — ``with_structured_output(schema)``
    returns a runnable whose ``invoke(messages)`` replays the script — but the
    entries come from the test instead of being derived from the prompt, which
    enables fault injection and retry assertions.

    Script entries (consumed in order, one per structured-output invocation):

    * ``{"valid": value}`` — return ``value`` validated against the schema:
      dicts are passed through ``schema.model_validate`` and the resulting
      model instance is returned; a ``schema`` instance passes through as-is.
    * ``{"invalid": value}`` — the payload is returned unvalidated, so the
      caller's schema validation (``app.llm.client.call_structured``) fails
      and drives its exactly-one-retry loop, mimicking a model that answers
      off-schema. Provide payloads that genuinely violate the schema, e.g.
      missing or wrong-typed fields; a payload that validates cleanly fails
      the test loudly (test-authoring bug).
    * a bare callable ``f(messages_text, context) -> value`` — treated as
      ``{"valid": f(...)}``. The inner ``value`` of a valid/invalid entry may
      itself be a callable with the same signature. ``messages_text`` is the
      flattened prompt text; ``context`` is the text inside its
      ``<<<CONTEXT>>>...<<<END_CONTEXT>>> block (``""`` if absent).
    * ``{"schema": SchemaName, "valid"/"invalid": value}`` — a *schema-tagged*
      entry: only invocations bound to that schema class name consume it;
      other schemas pass over it transparently. Use tagged entries to script
      one schema while the rest of the pipeline runs on defaults, e.g.
      ``[{"schema": "PreferenceWeights", "invalid": {"anc": "loud"}},
      {"schema": "PreferenceWeights", "invalid": {"anc": "loud"}}]`` drives
      the weights call to its second (final) failure while the intent, plan,
      and narration calls use the normal mock handlers.

    When an invocation finds no consumable entry (script exhausted, or every
    remaining entry is tagged for another schema), it falls back to
    ``MockChatLLM``'s built-in deterministic handler for that schema instead
    of failing — so tests script only the calls under test.

    ``calls`` records ``(schema_name, script_index)`` per structured-output
    invocation; fallback invocations record ``None`` as the index, letting
    tests assert exact retry counts, e.g.
    ``assert fake.calls == [("IntentExtraction", 0), ("IntentExtraction", 1)]``
    (exactly-one-retry).
    """

    def __init__(self, script: list[ScriptedEntry]) -> None:
        self._script: list[ScriptedEntry] = list(script)
        self._cursor: int = 0
        self.calls: list[tuple[str, int | None]] = []

    def with_structured_output(self, schema: Any) -> Any:
        """Return a runnable exposing ``invoke(messages)`` — the exact surface
        ``app.llm.client.call_structured`` consumes."""
        fake = self

        class _Bound:
            def invoke(self, messages: Any) -> Any:
                return fake._next(schema, messages)

        return _Bound()

    def _default_invoke(self, schema: Any, messages: Any) -> Any:
        """Delegate an unscripted invocation to ``MockChatLLM``'s default handlers."""
        from app.llm.client import MockChatLLM  # lazy: no app import at collection time

        return MockChatLLM().with_structured_output(schema).invoke(messages)

    def _next(self, schema: Any, messages: Any) -> Any:
        """Consume the next consumable script entry and resolve it against ``schema``."""
        schema_name = getattr(schema, "__name__", None) or type(schema).__name__

        index: int | None = None
        entry: ScriptedEntry | None = None
        scan = self._cursor
        while scan < len(self._script):
            candidate = self._script[scan]
            tag = candidate.get("schema") if isinstance(candidate, dict) else None
            if tag is None or tag == schema_name:
                index = scan
                entry = candidate
                break
            scan += 1  # tagged for a different schema: transparent to this call
        if entry is None:
            # Unscripted schema (or exhausted script): default mock behavior so
            # tests script only the schema under test.
            self.calls.append((schema_name, None))
            return self._default_invoke(schema, messages)
        self._cursor = index + 1
        self.calls.append((schema_name, index))

        messages_text = _messages_text(messages)
        context = _extract_context(messages_text)

        payload: Any
        if callable(entry):
            payload = entry(messages_text, context)
            expect_valid = True
        elif isinstance(entry, dict) and set(entry) in (
            {"valid"},
            {"invalid"},
            {"schema", "valid"},
            {"schema", "invalid"},
        ):
            raw = entry["valid"] if "valid" in entry else entry["invalid"]
            payload = raw(messages_text, context) if callable(raw) else raw
            expect_valid = "valid" in entry
        else:
            raise AssertionError(
                f"ScriptedFakeLLM: malformed script entry at index {index}: "
                f"{entry!r} (expected {{'valid': ...}}, {{'invalid': ...}}, "
                "{'schema': ..., 'valid'/'invalid': ...} or a callable)"
            )

        try:
            already_model = isinstance(payload, schema)
        except TypeError:  # schema is not a plain class (e.g. Annotated[...])
            already_model = False
        if expect_valid:
            if already_model:
                return payload
            return schema.model_validate(payload)

        # 'invalid' entry: return the payload UNVALIDATED so the D8 wrapper's
        # own schema validation fails and drives its exactly-one-retry loop
        # (raising inside invoke() would bypass ``call_structured``'s retry
        # machinery entirely). A payload that actually validates cleanly is a
        # test-authoring bug and fails loudly instead.
        try:
            schema.model_validate(payload)
        except ValidationError:
            return payload
        raise AssertionError(
            f"ScriptedFakeLLM: script entry at index {index} was marked 'invalid' "
            f"but validates cleanly against {schema_name}: {payload!r}"
        )


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force mock LLM mode with no credentials; reset any cached LLM client.

    Use explicitly in tests (and test modules) that touch the LLM layer:
    sets ``LLM_MODE=mock`` and clears ``OPENCODE_API_KEY`` / ``LLM_MODEL``
    for the duration of the test. ``app.llm.client`` is imported lazily so
    this fixture also works before that module exists.
    """
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    try:
        from app.llm.client import reset_llm_cache
    except (ImportError, AttributeError):
        # app.llm.client is produced by a concurrent wave; nothing to reset yet.
        return
    reset_llm_cache()


@pytest.fixture
def fake_llm_factory(monkeypatch: pytest.MonkeyPatch) -> FakeLLMFactory:
    """Return a factory patching the LLM factory to a scripted fake.

    The fake replaces ``app.llm.client.get_llm`` AND the ``get_llm`` binding
    inside ``app.graph.nodes`` (nodes import the name directly, so patching
    the client module alone would not reach the graph). Both are restored at
    teardown by ``monkeypatch``.

    Usage::

        fake = fake_llm_factory([{"invalid": {}}, {"valid": {"category": "headphones"}}])
        # ... run the code under test ...
        assert fake.calls == [("IntentExtraction", 0), ("IntentExtraction", 1)]
    """

    def factory(script: list[ScriptedEntry]) -> ScriptedFakeLLM:
        import app.graph.nodes as graph_nodes  # lazy: keep collection import-free
        import app.llm.client as llm_client

        fake = ScriptedFakeLLM(script)
        monkeypatch.setattr(llm_client, "get_llm", lambda: fake)
        if hasattr(graph_nodes, "get_llm"):
            monkeypatch.setattr(graph_nodes, "get_llm", lambda: fake)
        return fake

    return factory


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """httpx async client bound to the FastAPI app (imported lazily).

    ``app.main`` is produced by a later wave; importing inside the fixture
    body keeps collection of unrelated test files working until it lands.
    """
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def valid_product_ids() -> set[str]:
    """The four canonical catalog ids referenced by DSL/UI-plan tests.

    Hard-coded on purpose: the catalog dataset arrives from another agent
    and must not be imported here.
    """
    return {"aurora-hush-pro", "cloudline-air", "skyline-hush", "volt-enduro-70"}


async def collect_sse(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    """Parse a streaming httpx SSE response into ``(event, data_dict)`` tuples.

    Accumulates ``response.aiter_text()`` chunks (robust to partial frames),
    splits frames on ``"\\n\\n"`` and lines on ``event:`` / ``data:`` prefixes.
    Usage::

        from tests.conftest import collect_sse

        async with client.stream("POST", "/api/chat", json=payload) as response:
            events = await collect_sse(response)
    """
    events: list[tuple[str, dict[str, Any]]] = []
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            parsed = _parse_sse_frame(frame)
            if parsed is not None:
                events.append(parsed)
    tail = buffer.strip("\n")
    if tail:
        parsed = _parse_sse_frame(tail)
        if parsed is not None:
            events.append(parsed)
    return events


def _parse_sse_frame(frame: str) -> tuple[str, dict[str, Any]] | None:
    """Parse one ``event:``/``data:`` frame; ``None`` if it carries neither."""
    event_name = ""
    data_lines: list[str] = []
    for line in frame.split("\n"):
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    if not event_name and not data_lines:
        return None
    data_text = "\n".join(data_lines)
    if not data_text:
        return event_name, {}
    try:
        data = json.loads(data_text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"collect_sse: non-JSON data line in frame {frame!r}") from exc
    if not isinstance(data, dict):
        raise AssertionError(f"collect_sse: expected a JSON object in frame {frame!r}")
    return event_name, data
