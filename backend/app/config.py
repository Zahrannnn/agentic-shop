"""Environment-driven settings for the agentic-shop backend.

Constitution principle II: model, base URL, and API key come exclusively from
the environment. Nothing here hard-codes a model name or key.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: The only valid ``LLM_MODE`` values (validated case-insensitively).
_LLM_MODES: frozenset[str] = frozenset({"mock", "real"})

#: The only valid ``LLM_API_STYLE`` values (validated case-insensitively).
_LLM_API_STYLES: frozenset[str] = frozenset({"auto", "responses"})


class Settings(BaseSettings):
    """Process settings loaded from environment (and optional .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_MODE: str = "mock"
    LLM_MODEL: str = ""
    OPENCODE_BASE_URL: str = ""
    OPENCODE_API_KEY: str = ""
    #: "auto" (default) or "responses" for gateway models that only expose
    #: the OpenAI Responses API (e.g. muse-spark on OpenCode Zen).
    LLM_API_STYLE: str = "auto"
    #: Comma-separated browser origins allowed to call the API from a browser
    #: (CORS; architecture-review fix). Defaults are the Next.js dev servers.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("LLM_MODE", mode="after")
    @classmethod
    def _validate_llm_mode(cls, value: str) -> str:
        """Only ``mock`` / ``real`` (case-insensitive, stripped); normalize.

        A typo'd mode (``rel``) must fail at settings construction — the same
        fail-fast spirit as ``require_real_config``, one step earlier.
        """
        normalized = value.strip().lower()
        if normalized not in _LLM_MODES:
            allowed = ", ".join(sorted(_LLM_MODES))
            raise ValueError(f"LLM_MODE must be one of: {allowed} (got {value!r})")
        return normalized

    @field_validator("LLM_API_STYLE", mode="after")
    @classmethod
    def _validate_llm_api_style(cls, value: str) -> str:
        """Only ``auto`` / ``responses`` (case-insensitive, stripped); normalize."""
        normalized = value.strip().lower()
        if normalized not in _LLM_API_STYLES:
            allowed = ", ".join(sorted(_LLM_API_STYLES))
            raise ValueError(f"LLM_API_STYLE must be one of: {allowed} (got {value!r})")
        return normalized

    @property
    def is_mock(self) -> bool:
        if self.LLM_MODE != "real":
            return True
        return not (self.LLM_MODEL and self.OPENCODE_API_KEY)

    @property
    def allowed_origins(self) -> list[str]:
        """Parsed CORS origin allowlist (whitespace-tolerant, empties dropped)."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached process settings."""
    return Settings()


def require_real_config(settings: Settings | None = None) -> None:
    """Fail fast when LLM_MODE=real lacks the required gateway config.

    Called at app startup so misconfiguration surfaces immediately instead of
    mid-conversation.
    """
    s = settings or get_settings()
    if s.LLM_MODE.strip().lower() != "real":
        return
    missing = [name for name in ("LLM_MODEL", "OPENCODE_API_KEY") if not getattr(s, name)]
    if missing:
        raise RuntimeError(
            "LLM_MODE=real requires configured: " + ", ".join(missing) + ". "
            "Set them in the environment or .env, or use LLM_MODE=mock."
        )
