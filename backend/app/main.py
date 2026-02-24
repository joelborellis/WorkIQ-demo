"""
FastAPI application factory.

Entry points
────────────
  Local dev:  python main.py            (hot-reload via uvicorn)
  Production: uvicorn app.main:app --host 0.0.0.0 --port 8000
  Docker:     CMD in Dockerfile invokes the line above
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routes import auth as auth_router
from app.routes import copilot as copilot_router
from app.services.auth import AuthService
from app.services.copilot import CopilotService
from app.services.graph import GraphService
from app.services.retrieval import RetrievalService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise long-lived services once at startup and store them on
    ``app.state`` so every request can access them via ``request.app.state``.
    """
    settings = get_settings()

    app.state.settings = settings
    app.state.auth_service = AuthService(settings)
    app.state.copilot_service = CopilotService()
    app.state.graph_service = GraphService()
    app.state.retrieval_service = RetrievalService()
    # Server-side MSAL token cache store.
    # Maps cache_key (UUID) → serialised MSAL cache string.
    # Kept here instead of in the session cookie to stay well under the ~4 KB
    # browser cookie size limit.  Does not survive a server restart (dev only).
    app.state.token_cache_store: dict[str, str] = {}

    logger.info(
        "WorkIQ API started  tenant=%s  client=%s  redirect_uri=%s  debug=%s",
        settings.tenant_id,
        settings.client_id,
        settings.redirect_uri,
        settings.debug,
    )
    yield
    logger.info("WorkIQ API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "WorkIQ backend — routes M365 Copilot Chat queries through the "
            "Graph beta API using the OAuth 2.0 auth-code flow (confidential client)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Session middleware ─────────────────────────────────────────────────────
    # Signs and verifies session cookies using SECRET_KEY.
    # Sessions are stored entirely in the cookie (signed, not encrypted by default).
    # For production, consider https_only=True and a shorter max_age.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="workiq_session",
        max_age=8 * 60 * 60,        # 8 hours
        same_site="lax",
        https_only=False,           # Set True in production (requires HTTPS)
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # allow_credentials=True is required for session cookies to be sent
    # cross-origin.  allow_origins must NOT be "*" when credentials are used.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(auth_router.router,    prefix="/auth",    tags=["Auth"])
    app.include_router(copilot_router.router, prefix="/api/v1",  tags=["Copilot"])

    # ── Infrastructure ────────────────────────────────────────────────────────
    @app.get("/health", tags=["Infrastructure"], include_in_schema=False)
    async def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
