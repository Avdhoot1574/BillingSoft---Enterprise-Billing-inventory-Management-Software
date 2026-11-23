from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-secret-change-me-dev-only-secret"
ROOT_DIR = Path(__file__).resolve().parents[2]  # project root (where .env lives)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_env: str = "dev"  # dev | test | staging | production

    # Database: prefer DATABASE_URL if set; otherwise derive from Supabase credentials
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None

    @property
    def effective_database_url(self) -> str:
        """Resolve the database URL: DATABASE_URL > Supabase-derived > default."""
        if self.database_url:
            return self.database_url
        if self.supabase_url and self.supabase_secret_key:
            return self._supabase_to_postgres_url()
        # Fallback default (local dev)
        return "postgresql+psycopg://postgres:postgres@localhost:5432/billing"

    def _supabase_to_postgres_url(self) -> str:
        """Convert Supabase URL + secret key into a PostgreSQL connection string.

        Supabase URL format: https://<project-ref>.supabase.co
        Derived PostgreSQL URL: postgresql+psycopg://postgres.<project-ref>:<secret-key>@db.<project-ref>.supabase.co:5432/postgres
        """
        parsed = urlsplit(self.supabase_url)
        host = parsed.hostname or ""
        parts = host.split(".")
        if len(parts) >= 3 and parts[-2] == "supabase" and parts[-1] == "co":
            project_ref = parts[0]
            return (
                f"postgresql+psycopg://postgres.{project_ref}:{self.supabase_secret_key}"
                f"@db.{project_ref}.supabase.co:5432/postgres"
            )
        # If we can't parse the project ref, use the host as-is
        return (
            f"postgresql+psycopg://postgres:{self.supabase_secret_key}"
            f"@{host}:5432/postgres"
        )

    jwt_secret: str = _DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    invitation_valid_days: int = 7
    # Dev/test convenience until the email outbox exists. NEVER enable in production.
    expose_invitation_tokens: bool = False

    cors_origins: list[str] = ["*"]

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.app_env in ("staging", "production"):
            if self.jwt_secret == _DEV_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters")
            if self.expose_invitation_tokens:
                raise ValueError("EXPOSE_INVITATION_TOKENS must be false outside dev/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
