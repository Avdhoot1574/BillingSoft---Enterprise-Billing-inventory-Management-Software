from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-secret-change-me-dev-only-secret"
ROOT_DIR = Path(__file__).resolve().parents[2]  # project root (where .env lives)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_env: str = "dev"  # dev | test | staging | production
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/billing"

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
