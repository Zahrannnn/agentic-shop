"""FastAPI application factory for the agentic-shop backend (Phase 1).

``create_app`` fails fast on a misconfigured real LLM mode (research R8:
``LLM_MODE=real`` without model/key must surface at startup, not at first
request) and mounts the API router (``/health``, ``POST /api/chat``).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import require_real_config


def create_app() -> FastAPI:
    """Build the app: fail-fast config check, then mount the API router."""
    require_real_config()
    application = FastAPI(title="agentic-shop backend")
    application.include_router(router)
    return application


app = create_app()
