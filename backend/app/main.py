"""FastAPI application factory for the agentic-shop backend (Phase 1).

``create_app`` fails fast on a misconfigured real LLM mode (research R8:
``LLM_MODE=real`` without model/key must surface at startup, not at first
request), installs the CORS allowlist from ``Settings.ALLOWED_ORIGINS``
(architecture-review fix: the Next.js frontend is a browser client, so
cross-origin requests must be answered correctly), and mounts the API
router (``/health``, ``POST /api/chat``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings, require_real_config


def create_app() -> FastAPI:
    """Build the app: fail-fast config check, CORS allowlist, API router."""
    require_real_config()
    settings = get_settings()
    application = FastAPI(title="agentic-shop backend")
    # Credentials stay off: the API is keyless from the browser's point of
    # view and a wildcard-with-credentials would be incoherent anyway. The
    # origin allowlist is explicit (never "*") so preflights from other
    # origins are rejected.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=False,
    )
    application.include_router(router)
    return application


app = create_app()
