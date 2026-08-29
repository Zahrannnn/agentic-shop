"""Environment-driven settings for the agentic-shop backend.

Constitution principle II: model, base URL, and API key come exclusively from
the environment. Nothing here hard-codes a model name or key.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def is_mock(self) -> bool:
        if self.LLM_MODE.strip().lower() != "real":
            return True
        return not (self.LLM_MODEL and self.OPENCODE_API_KEY)


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
