"""Supabase client initialization.

Provides a Supabase client (via the official supabase-py package) for Supabase-specific
operations such as storage, auth, and realtime subscriptions. The main application database
layer continues to use SQLAlchemy with a PostgreSQL connection derived from Supabase
credentials.

Environment variables (from .env):
    SUPABASE_URL        - https://<project-ref>.supabase.co
    SUPABASE_SECRET_KEY - service role key (keep secret!)
"""

from functools import lru_cache
from typing import Optional

from app.core.config import get_settings

try:
    from supabase import create_client, Client
except ImportError:  # pragma: no cover - supabase package may not be installed
    create_client = None  # type: ignore[assignment]
    Client = None  # type: ignore[assignment]


_supabase_client: Optional["Client"] = None


def get_supabase_client() -> Optional["Client"]:
    """Return a cached Supabase client, or None if the package isn't installed or
    SUPABASE_URL / SUPABASE_SECRET_KEY are not configured."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if create_client is None:
        return None

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        return None

    _supabase_client = create_client(settings.supabase_url, settings.supabase_secret_key)
    return _supabase_client


@lru_cache
def get_supabase_client_cached() -> Optional["Client"]:
    """LRU-cached variant of get_supabase_client for dependency injection."""
    return get_supabase_client()
