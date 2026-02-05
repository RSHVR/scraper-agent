"""API key generation and validation utilities."""

import secrets
from datetime import datetime, timezone
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .supabase_client import get_supabase_admin_client
from ..utils.logger import logger


# Argon2 hasher with secure defaults
ph = PasswordHasher()


def generate_api_key(prefix: str = "sk_") -> tuple[str, str, str]:
    """Generate a new API key.

    Args:
        prefix: Key prefix for identification (default: "sk_" for secret key)

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete API key to give to the user (shown once)
        - key_prefix: First 8 chars for identification (stored in DB)
        - key_hash: Argon2 hash of the key (stored in DB)
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}{random_part}"
    key_prefix = full_key[:12]  # Store prefix for identification
    key_hash = ph.hash(full_key)

    return full_key, key_prefix, key_hash


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its hash.

    Args:
        key: The API key to verify
        key_hash: The stored Argon2 hash

    Returns:
        True if the key matches, False otherwise
    """
    try:
        ph.verify(key_hash, key)
        return True
    except VerifyMismatchError:
        return False
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return False


async def validate_api_key(api_key: str) -> Optional[dict]:
    """Validate an API key against the database.

    Args:
        api_key: The API key to validate

    Returns:
        Dict with user_id and scopes if valid, None otherwise
    """
    if not api_key or len(api_key) < 12:
        return None

    try:
        supabase = get_supabase_admin_client()
        key_prefix = api_key[:12]

        # Find keys with matching prefix
        response = supabase.table("api_keys").select(
            "id, user_id, key_hash, scopes, is_active, expires_at"
        ).eq("key_prefix", key_prefix).eq("is_active", True).execute()

        if not response.data:
            return None

        # Check each potential match (usually just one)
        for key_record in response.data:
            # Check expiration
            if key_record.get("expires_at"):
                expires_at = datetime.fromisoformat(key_record["expires_at"].replace("Z", "+00:00"))
                if expires_at < datetime.now(timezone.utc):
                    continue

            # Verify the key hash
            if verify_api_key(api_key, key_record["key_hash"]):
                # Update last_used_at
                supabase.table("api_keys").update({
                    "last_used_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", key_record["id"]).execute()

                return {
                    "user_id": key_record["user_id"],
                    "scopes": key_record.get("scopes", ["scrape:read", "scrape:write"]),
                    "key_id": key_record["id"]
                }

        return None

    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None
