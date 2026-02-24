from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Azure Entra ID ────────────────────────────────────────────────────────
    tenant_id: str
    client_id: str
    client_secret: str

    # ── Session ───────────────────────────────────────────────────────────────
    # Used by Starlette SessionMiddleware to sign session cookies.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    # Or use the Setup-AppRegistration.ps1 script which generates one for you.
    secret_key: str

    # OAuth redirect URI — must match exactly what is registered in Entra ID.
    # Points to the BACKEND (not the frontend): <backend_url>/auth/callback
    redirect_uri: str = "http://localhost:8000/auth/callback"

    # Frontend URL — where the backend redirects the user after sign-in/out.
    frontend_url: str = "http://localhost:5173"

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Stored as a plain str so pydantic-settings does not attempt to JSON-parse
    # it.  The `allowed_origins` computed field converts it to the list that
    # CORSMiddleware expects.  Use a comma-separated value in .env:
    #   ALLOWED_ORIGINS=http://localhost:5173,https://app.contoso.com
    allowed_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias=AliasChoices("allowed_origins", "ALLOWED_ORIGINS"),
    )

    @computed_field
    @property
    def allowed_origins(self) -> list[str]:
        return [s.strip() for s in self.allowed_origins_raw.split(",") if s.strip()]

    # ── App metadata ─────────────────────────────────────────────────────────
    app_name: str = "WorkIQ API"
    app_version: str = "0.1.0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
