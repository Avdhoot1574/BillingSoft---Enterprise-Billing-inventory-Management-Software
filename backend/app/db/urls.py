"""Database URL helpers shared by the helper scripts and the test suite.

Deliberately dependency-free (no SQLAlchemy / dotenv) so it can be imported before anything else.
Convention: the test database is the main database name + "_test"  (billing -> billing_test).
"""
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/billing"


def read_dotenv(path: Path | None = None) -> dict[str, str]:
    path = path or ROOT_DIR / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def setting(name: str, default: str | None = None) -> str | None:
    """Environment variable first, then .env, then default."""
    return os.environ.get(name) or read_dotenv().get(name) or default


def _supabase_to_postgres_url(supabase_url: str, supabase_secret_key: str) -> str:
    """Convert Supabase URL + secret key into a PostgreSQL connection string.

    Supabase URL format: https://<project-ref>.supabase.co
    Derived PostgreSQL URL: postgresql+psycopg://postgres.<project-ref>:<secret-key>@db.<project-ref>.supabase.co:5432/postgres
    """
    parsed = urlsplit(supabase_url)
    host = parsed.hostname or ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] == "supabase" and parts[-1] == "co":
        project_ref = parts[0]
        return (
            f"postgresql+psycopg://postgres.{project_ref}:{supabase_secret_key}"
            f"@db.{project_ref}.supabase.co:5432/postgres"
        )
    return (
        f"postgresql+psycopg://postgres:{supabase_secret_key}"
        f"@{host}:5432/postgres"
    )


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def with_database(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


def main_url() -> str:
    """Resolve the database URL: DATABASE_URL > Supabase-derived > default."""
    explicit = setting("DATABASE_URL")
    if explicit:
        return explicit
    supabase_url = setting("SUPABASE_URL")
    supabase_secret_key = setting("SUPABASE_SECRET_KEY")
    if supabase_url and supabase_secret_key:
        return _supabase_to_postgres_url(supabase_url, supabase_secret_key)
    return DEFAULT_URL


def test_url() -> str:
    explicit = setting("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = main_url()
    return with_database(url, f"{database_name(url)}_test")


def maintenance_url(url: str) -> str:
    """Same server and credentials, but the built-in 'postgres' database (needed for CREATE DATABASE)."""
    return with_database(url, "postgres")
