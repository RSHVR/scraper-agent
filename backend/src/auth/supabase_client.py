"""Supabase client singleton for authentication operations."""

from functools import lru_cache
from supabase import create_client, Client

from ..config import settings
from ..utils.logger import logger


@lru_cache()
def get_supabase_client() -> Client:
    """Get Supabase client using the anon key.

    This client is for public operations like user registration/login.
    Returns a cached singleton instance.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise ValueError("Supabase URL and anon key must be configured")

    logger.info("Initializing Supabase client (anon)")
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key
    )


@lru_cache()
def get_supabase_admin_client() -> Client:
    """Get Supabase client using the service role key.

    This client has admin privileges and should only be used for:
    - Server-side operations
    - API key validation
    - Session ownership management

    Returns a cached singleton instance.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        raise ValueError("Supabase URL and service key must be configured")

    logger.info("Initializing Supabase admin client")
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )
