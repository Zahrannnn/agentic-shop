"""US5 config tests: keyless defaults, fail-fast real mode, secret hygiene.

``app.config`` is the constitution-II doorway: model, base URL, and API key
come exclusively from the environment; ``LLM_MODE=mock`` (the default) must
let everything run with no credentials, and ``LLM_MODE=real`` without them
must fail fast at startup — never mid-conversation.
"""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings, require_real_config

pytestmark = pytest.mark.usefixtures("mock_settings")

_ENV_KEYS: tuple[str, ...] = ("LLM_MODE", "LLM_MODEL", "OPENCODE_BASE_URL", "OPENCODE_API_KEY")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every settings variable so defaults are actually exercised."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_get_settings_defaults_to_mock_when_env_empty(clean_env) -> None:
    """No environment at all -> mock mode, empty credentials, keyless run."""
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.LLM_MODE == "mock"
        assert settings.is_mock is True
        assert settings.LLM_MODEL == ""
        assert settings.OPENCODE_API_KEY == ""
        assert settings.OPENCODE_BASE_URL == ""
    finally:
        get_settings.cache_clear()  # never leak a cached instance into other tests


def test_require_real_config_passes_in_mock_mode(clean_env) -> None:
    """Mock mode never demands credentials (the whole suite runs keyless)."""
    settings = Settings(LLM_MODE="mock", _env_file=None)
    assert settings.is_mock is True
    assert require_real_config(settings) is None


def test_require_real_config_raises_naming_missing_vars(clean_env) -> None:
    """LLM_MODE=real without model/key fails fast, naming both variables."""
    settings = Settings(LLM_MODE="real", _env_file=None)
    with pytest.raises(RuntimeError) as excinfo:
        require_real_config(settings)
    message = str(excinfo.value)
    assert "LLM_MODEL" in message
    assert "OPENCODE_API_KEY" in message
    assert "LLM_MODE=mock" in message  # the escape hatch is advertised


def test_require_real_config_passes_when_both_set(clean_env) -> None:
    settings = Settings(
        LLM_MODE="real",
        LLM_MODEL="test-model",
        OPENCODE_API_KEY="test-key",
        _env_file=None,
    )
    assert settings.is_mock is False
    assert require_real_config(settings) is None


async def test_health_never_echoes_secrets(client) -> None:
    """The health payload is exactly {status, mode} — no key names or values."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.text
    assert response.json() == {"status": "ok", "mode": "mock"}
    assert set(response.json()) == {"status", "mode"}
    # Explicit secret-hygiene asserts (US5): neither the variable names nor
    # any configured value may appear in the response.
    assert "OPENCODE_API_KEY" not in body
    assert "LLM_MODEL" not in body
    assert "OPENCODE_BASE_URL" not in body
