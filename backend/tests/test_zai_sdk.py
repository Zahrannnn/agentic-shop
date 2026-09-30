"""LLM_SDK=zai — the official Z.ai SDK transport (app/llm/zai adapter).

Hermetic by construction: building the client never touches the network,
so these tests run with the real ``ZaiClient`` object and a placeholder
key — the failure mode under a wrong key (a typed 401) is documented in
the manual real-mode runs, not here.
"""

from __future__ import annotations

from typing import Any

import pytest
from zai import ZaiClient

pytestmark = pytest.mark.usefixtures("mock_settings")


def _reset(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    from app.config import get_settings
    from app.llm.client import reset_llm_cache

    defaults = {
        "LLM_MODE": "real",
        "LLM_MODEL": "glm-5.3-flash",
        "OPENCODE_BASE_URL": "https://api.z.ai/api/paas/v4",
        "OPENCODE_API_KEY": "k-test",
        "LLM_API_STYLE": "auto",
        "LLM_SDK": "zai",
    }
    defaults.update(env)
    for name, value in defaults.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    reset_llm_cache()


class TestZaiAdapter:
    def test_real_mode_with_sdk_builds_chatzai_with_zai_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.llm.client import get_llm
        from app.llm.zai import ChatZai

        _reset(monkeypatch)
        llm = get_llm()
        assert isinstance(llm, ChatZai)
        assert llm.model_name == "glm-5.3-flash"
        assert isinstance(llm.root_client, ZaiClient)
        assert llm.temperature == 0

    def test_openai_sdk_default_builds_plain_chat_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from langchain_openai import ChatOpenAI

        from app.llm.client import get_llm
        from app.llm.zai import ChatZai

        _reset(monkeypatch, LLM_SDK="openai")
        llm = get_llm()
        assert not isinstance(llm, ChatZai)
        assert isinstance(llm, ChatOpenAI)

    def test_structured_output_pins_function_calling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The D8 wrapper calls ``with_structured_output(schema)`` with no
        method — the adapter must pin function_calling (the Z.ai SDK lacks
        the json_schema parse helpers the default method requires)."""
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel

        from app.llm.client import get_llm

        class Probe(BaseModel):
            category: str

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            ChatOpenAI,
            "with_structured_output",
            lambda self, schema, **kwargs: captured.update(kwargs, schema=schema),
        )
        _reset(monkeypatch)
        get_llm().with_structured_output(Probe)
        assert captured["method"] == "function_calling"
        assert captured["schema"] is Probe

    def test_llm_sdk_setting_is_validated(self) -> None:
        from app.config import Settings

        with pytest.raises(Exception, match="LLM_SDK"):
            Settings(LLM_SDK="openai2", _env_file=None)

    def test_cache_key_includes_sdk_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.llm.client import get_llm
        from app.llm.zai import ChatZai

        _reset(monkeypatch, LLM_SDK="openai")
        plain = get_llm()
        _reset(monkeypatch, LLM_SDK="zai")
        zai_llm = get_llm()
        assert not isinstance(plain, ChatZai)
        assert isinstance(zai_llm, ChatZai)
