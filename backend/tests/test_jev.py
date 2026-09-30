"""D9 — TypeSafe Jev judgment layer: questions, mocks, transport, graph swap.

Covers (specs/003-jev-and-a2ui, PR 1):

- ``build_intent_questions`` shape and purity (catalog categories + ``unclear``
  choice; one 4-level score rubric per scorable attribute);
- ``MockJevClient`` determinism and equivalence with the LLM-mock regex
  baseline — both derive from ``app.llm.intent_rules``;
- ``HttpxJevClient`` against an ``httpx.MockTransport``: request shape,
  success parsing, salience/confidence mapping, the single retry on
  429/transport/schema failure, hard failures raising :class:`JevError`;
- the factory modes (``off``/``mock`` offline, ``real`` fail-fast without key);
- the intent-node swap: ``JEV_MODE=mock`` produces the same wire output as the
  LLM path for the MVP message; chip and follow-up fast-paths and
  ``JEV_MODE=off`` never call Jev;
- API mapping: a raised :class:`JevError` ends the stream as one terminal
  ``error`` frame with code ``jev`` and no ``turn_end``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from tests.conftest import collect_sse

pytestmark = pytest.mark.usefixtures("mock_settings")


# ---------------------------------------------------------------------------
# Env / cache juggling
# ---------------------------------------------------------------------------


def _reset_caches() -> None:
    from app.config import get_settings
    from app.llm.jev import reset_jev_cache

    get_settings.cache_clear()
    reset_jev_cache()


@pytest.fixture
def jev_env(monkeypatch: pytest.MonkeyPatch):
    """Configure ``JEV_*`` env vars, clearing the settings + Jev caches.

    ``get_settings`` is ``lru_cache``d and reads env at construction, so every
    reconfiguration must clear both caches (and again at teardown, so no
    ``JEV_MODE`` from this test leaks into a later one via a cached Settings).
    """

    def configure(mode: str, **overrides: str) -> None:
        monkeypatch.setenv("JEV_MODE", mode)
        for name, value in overrides.items():
            monkeypatch.setenv(name, value)
        _reset_caches()

    yield configure
    _reset_caches()


# ---------------------------------------------------------------------------
# Response fixtures (documented wire shapes)
# ---------------------------------------------------------------------------


def _choice_answer(choice: str, confidence: float = 0.9) -> dict[str, Any]:
    return {
        "choice": choice,
        "probabilities": {choice: 0.9, "unclear": 0.1},
        "confidence": confidence,
    }


def _score_answer(score: float, confidence: float = 0.9) -> dict[str, Any]:
    return {
        "score": score,
        "legend": {"0": "unmentioned", "1": "mentioned", "2": "important", "3": "critical"},
        "probabilities": {str(int(score)): 1.0},
        "confidence": confidence,
    }


def _response_json(answers: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "jev-latest",
        "answers": answers,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _default_intent_answers(
    category: str = "headphones", confidence: float = 0.9
) -> dict[str, Any]:
    return {
        "category": _choice_answer(category, confidence),
        "p_anc": _score_answer(3.0),
        "p_comfort": _score_answer(2.0),
        "p_battery": _score_answer(0.0),
        "p_sound": _score_answer(0.0),
        "p_value": _score_answer(0.0),
    }


# ---------------------------------------------------------------------------
# Question building
# ---------------------------------------------------------------------------


class TestBuildIntentQuestions:
    def test_category_choice_covers_catalog_categories_and_unclear(self) -> None:
        from app.llm.jev import UNCLEAR_CATEGORY, build_intent_questions

        category = build_intent_questions(["earbuds", "headphones"])["category"]
        assert category["type"] == "choice"
        assert set(category["criteria"]) == {"earbuds", "headphones", UNCLEAR_CATEGORY}
        described = [isinstance(text, str) and bool(text) for text in category["criteria"].values()]
        assert all(described)  # every option needs a criteria description

    def test_one_score_rubric_per_scorable_attribute(self) -> None:
        from app.llm.jev import PRIORITY_KEYS, PRIORITY_RUBRIC, build_intent_questions

        questions = build_intent_questions(["headphones"])
        assert set(questions) == {"category", *(f"p_{key}" for key in PRIORITY_KEYS)}
        for key in PRIORITY_KEYS:
            score = questions[f"p_{key}"]
            assert score["type"] == "score"
            assert score["criteria"] == list(PRIORITY_RUBRIC)
            assert 2 <= len(score["criteria"]) <= 10  # API bound: 2–10 levels

    def test_pure_and_json_serializable(self) -> None:
        from app.llm.jev import build_intent_questions

        first = build_intent_questions(["earbuds", "headphones"])
        assert build_intent_questions(["earbuds", "headphones"]) == first
        assert json.loads(json.dumps(first)) == first


# ---------------------------------------------------------------------------
# Offline client
# ---------------------------------------------------------------------------


class TestMockJev:
    def test_mock_client_is_deterministic(self) -> None:
        from app.llm.jev import MockJevClient, build_intent_questions

        client = MockJevClient()
        questions = build_intent_questions(["earbuds", "headphones"])
        first = client.ask({"message": "noise cancelling headphones under $200"}, questions)
        second = client.ask({"message": "noise cancelling headphones under $200"}, questions)
        assert first.model_dump() == second.model_dump()

    def test_mock_answers_match_the_regex_baseline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Jev-mock ≡ LLM-mock for intent: same category/budget/priorities."""
        import app.llm.jev as jev_module
        from app.llm.jev import MockJevClient, jev_ask_intent

        monkeypatch.setattr(jev_module, "get_jev", lambda: MockJevClient())
        cases = [
            ("Best headphones for long flights under $200", "headphones", 200.0, {}),
            (
                "earbuds with great battery and noise cancelling",
                "earbuds",
                None,
                {"anc": 1.0, "battery": 1.0},
            ),
            ("cheap comfortable headphones", "headphones", None, {"comfort": 1.0, "value": 1.0}),
            ("something nice please", None, None, {}),
        ]
        for message, category, budget, priorities in cases:
            answers = jev_ask_intent(message, ["earbuds", "headphones"])
            assert answers.category == category, message
            assert answers.budget_usd == budget, message
            assert answers.priorities == priorities, message


# ---------------------------------------------------------------------------
# Real client over a scripted transport
# ---------------------------------------------------------------------------


def _httpx_client(handler: httpx.MockTransport) -> Any:
    from app.llm.jev import HttpxJevClient

    return HttpxJevClient(
        base_url="https://jev.test/v1/systemone",
        api_key="k-test",
        model="jev-latest",
        transport=handler,
    )


class TestHttpxJevClient:
    def test_success_parses_answers_and_request_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.llm.jev as jev_module
        from app.llm.jev import build_intent_questions, jev_ask_intent

        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("Authorization")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json=_response_json(_default_intent_answers()))

        client = _httpx_client(httpx.MockTransport(handler))
        monkeypatch.setattr(jev_module, "get_jev", lambda: client)

        answers = jev_ask_intent(
            "Best headphones for long flights under $200", ["earbuds", "headphones"]
        )

        assert captured["auth"] == "Bearer k-test"
        assert set(captured["payload"]) == {"state", "model", "questions"}
        assert captured["payload"]["model"] == "jev-latest"
        assert captured["payload"]["state"] == {
            "message": "Best headphones for long flights under $200"
        }
        assert captured["payload"]["questions"] == build_intent_questions(["earbuds", "headphones"])
        # score -> salience: 3 -> 1.0, 2 -> 2/3, 0 omitted; budget from the regex.
        assert answers.category == "headphones"
        assert answers.budget_usd == 200.0
        assert answers.priorities == {"anc": 1.0, "comfort": 2.0 / 3.0}

    def test_low_confidence_category_is_treated_as_unclear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.llm.jev as jev_module
        from app.llm.jev import jev_ask_intent

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=_response_json(_default_intent_answers(confidence=0.3))
            )
        )
        monkeypatch.setattr(jev_module, "get_jev", lambda: _httpx_client(transport))
        assert jev_ask_intent("some headphones", ["earbuds", "headphones"]).category is None

    def test_unclear_choice_maps_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import app.llm.jev as jev_module
        from app.llm.jev import jev_ask_intent

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=_response_json(_default_intent_answers(category="unclear", confidence=0.99)),
            )
        )
        monkeypatch.setattr(jev_module, "get_jev", lambda: _httpx_client(transport))
        assert jev_ask_intent("something nice", ["earbuds", "headphones"]).category is None

    def test_retry_once_on_429_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.llm.jev import RETRY_DELAY_SECONDS

        monkeypatch.setattr("app.llm.jev.time.sleep", lambda seconds: None)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return httpx.Response(429, json={"detail": "rate limited"})
            return httpx.Response(200, json=_response_json(_default_intent_answers()))

        response = _httpx_client(httpx.MockTransport(handler)).ask(
            {"message": "headphones"}, {"category": {"type": "choice"}}
        )
        assert response.answers["category"]["choice"] == "headphones"
        assert len(calls) == 2
        assert RETRY_DELAY_SECONDS > 0  # real mode backs off; tests patch the sleep

    def test_529_twice_raises_jev_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.llm.jev import JevError

        monkeypatch.setattr("app.llm.jev.time.sleep", lambda seconds: None)
        calls: list[int] = []
        transport = httpx.MockTransport(
            lambda request: (calls.append(1), httpx.Response(529, json={"detail": "overloaded"}))[1]
        )
        with pytest.raises(JevError, match="529"):
            _httpx_client(transport).ask({"message": "headphones"}, {})
        assert len(calls) == 2

    def test_401_fails_immediately_without_retry(self) -> None:
        from app.llm.jev import JevError

        calls: list[int] = []
        transport = httpx.MockTransport(
            lambda request: (calls.append(1), httpx.Response(401, json={"detail": "bad key"}))[1]
        )
        with pytest.raises(JevError, match="401"):
            _httpx_client(transport).ask({"message": "headphones"}, {})
        assert len(calls) == 1  # request-side errors are not retried

    def test_transport_error_retried_once_then_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.llm.jev import JevError

        monkeypatch.setattr("app.llm.jev.time.sleep", lambda seconds: None)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            raise httpx.ConnectError("connection refused")

        with pytest.raises(JevError, match="transport"):
            _httpx_client(httpx.MockTransport(handler)).ask({"message": "headphones"}, {})
        assert len(calls) == 2

    def test_invalid_response_schema_twice_raises(self) -> None:
        from app.llm.jev import JevError

        calls: list[int] = []
        transport = httpx.MockTransport(
            lambda request: (
                calls.append(1),
                httpx.Response(200, json={"unexpected": "shape"}),
            )[1]
        )
        with pytest.raises(JevError, match="schema validation"):
            _httpx_client(transport).ask({"message": "headphones"}, {})
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# Factory + settings validation
# ---------------------------------------------------------------------------


class TestFactoryAndConfig:
    def test_off_and_mock_build_the_offline_client(self, jev_env) -> None:
        from app.llm.jev import MockJevClient, get_jev

        jev_env("off")
        assert isinstance(get_jev(), MockJevClient)
        jev_env("mock")
        assert isinstance(get_jev(), MockJevClient)

    def test_real_without_key_fails_fast(self, jev_env) -> None:
        from app.llm.jev import get_jev

        jev_env("real")
        with pytest.raises(RuntimeError, match="JEV_API_KEY"):
            get_jev()

    def test_real_with_key_builds_httpx_client(self, jev_env) -> None:
        from app.llm.jev import HttpxJevClient, get_jev

        jev_env("real", JEV_API_KEY="k-live")
        assert isinstance(get_jev(), HttpxJevClient)

    def test_jev_mode_typo_rejected_at_settings_construction(self) -> None:
        from app.config import Settings

        with pytest.raises(ValidationError, match="JEV_MODE"):
            Settings(JEV_MODE="rel")

    def test_require_jev_config(self, jev_env) -> None:
        from app.config import require_jev_config

        jev_env("mock")
        require_jev_config()  # no raise
        jev_env("off")
        require_jev_config()  # no raise
        jev_env("real")
        with pytest.raises(RuntimeError, match="JEV_API_KEY"):
            require_jev_config()


# ---------------------------------------------------------------------------
# Graph integration
# ---------------------------------------------------------------------------


def _normalize_session(events: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, Any]]:
    """Blank out ``sessionId`` so two sessions' streams compare equal."""
    normalized: list[tuple[str, Any]] = []
    for event, data in events:
        if isinstance(data, dict) and "sessionId" in data:
            data = {**data, "sessionId": "<session>"}
        normalized.append((event, data))
    return normalized


class _CountingJev:
    """Wrap the real ``jev_ask_intent`` and record every call's message."""

    def __init__(self, graph_nodes) -> None:
        self._original = graph_nodes.jev_ask_intent
        self.calls: list[str] = []

    def __call__(self, message: str, categories: Any) -> Any:
        self.calls.append(message)
        return self._original(message, categories)


class TestIntentNodeSwap:
    async def test_jev_mock_matches_llm_mock_wire_output(self, client, jev_env) -> None:
        """The flagship equivalence: same message, same SSE output, both paths."""
        message = "Best headphones for long flights under $200"

        jev_env("off")
        async with client.stream(
            "POST", "/api/chat", json={"session_id": "jev-equiv-lllmmm", "message": message}
        ) as response:
            llm_events = await collect_sse(response)

        jev_env("mock")
        async with client.stream(
            "POST", "/api/chat", json={"session_id": "jev-equiv-jevjev", "message": message}
        ) as response:
            jev_events = await collect_sse(response)

        assert _normalize_session(jev_events) == _normalize_session(llm_events)
        assert llm_events[-1] == ("turn_end", {})

    async def test_chip_answer_skips_jev(self, client, jev_env, monkeypatch) -> None:
        import app.graph.nodes as graph_nodes

        jev_env("mock")
        counting = _CountingJev(graph_nodes)
        monkeypatch.setattr(graph_nodes, "jev_ask_intent", counting)
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "jev-chip-skip-01",
                "ui_action": {
                    "type": "select_preference",
                    "label": "Headphones",
                    "payload": {"value": "headphones"},
                },
            },
        ) as response:
            events = await collect_sse(response)

        assert counting.calls == []  # the chip IS the intent — no judgment call
        assert events[-1] == ("turn_end", {})

    async def test_followup_skips_jev(self, client, jev_env, monkeypatch) -> None:
        import app.graph.nodes as graph_nodes

        jev_env("mock")
        counting = _CountingJev(graph_nodes)
        monkeypatch.setattr(graph_nodes, "jev_ask_intent", counting)

        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "jev-followup-001",
                "message": "Best headphones for long flights under $200",
            },
        ) as response:
            await collect_sse(response)
        assert len(counting.calls) == 1  # turn 1 used the judgment layer

        async with client.stream(
            "POST",
            "/api/chat",
            json={"session_id": "jev-followup-001", "message": "compare the first two"},
        ) as response:
            events = await collect_sse(response)
        assert len(counting.calls) == 1  # follow-ups resolve deterministically
        assert events[-1] == ("turn_end", {})

    async def test_off_mode_never_calls_jev(self, client, jev_env, monkeypatch) -> None:
        import app.graph.nodes as graph_nodes

        jev_env("off")
        calls: list[str] = []
        monkeypatch.setattr(
            graph_nodes,
            "jev_ask_intent",
            lambda message, categories: calls.append(message),
        )
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "jev-off-mode-001",
                "message": "Best headphones for long flights under $200",
            },
        ) as response:
            events = await collect_sse(response)

        assert calls == []
        assert events[-1] == ("turn_end", {})

    async def test_jev_error_ends_stream_with_jev_code(self, client, jev_env, monkeypatch) -> None:
        from app.llm.jev import JevError

        jev_env("mock")

        def failing(message: str, categories: Any) -> Any:
            raise JevError("jev judgment failed twice (transport error)")

        monkeypatch.setattr("app.graph.nodes.jev_ask_intent", failing)
        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "session_id": "jev-error-path-01",
                "message": "Best headphones for long flights under $200",
            },
        ) as response:
            events = await collect_sse(response)

        event_names = [event for event, _ in events]
        assert events[-1][0] == "error"
        assert events[-1][1]["code"] == "jev"
        assert "turn_end" not in event_names
        assert "ui_update" not in event_names
