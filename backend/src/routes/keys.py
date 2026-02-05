"""API key management routes."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends

from ..auth.supabase_client import get_supabase_admin_client
from ..auth.dependencies import get_current_user
from ..auth.api_keys import generate_api_key
from ..models.auth import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyInfo,
    APIKeyList,
    AuthContext,
)
from ..utils.logger import logger

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.get("", response_model=APIKeyList)
async def list_api_keys(auth: AuthContext = Depends(get_current_user)):
    """List all API keys for the authenticated user."""
    try:
        supabase = get_supabase_admin_client()

        response = supabase.table("api_keys").select(
            "id, name, key_prefix, scopes, is_active, last_used_at, expires_at, created_at"
        ).eq("user_id", auth.user_id).order("created_at", desc=True).execute()

        keys = [
            APIKeyInfo(
                id=key["id"],
                name=key["name"],
                key_prefix=key["key_prefix"],
                scopes=key.get("scopes", []),
                is_active=key["is_active"],
                last_used_at=key.get("last_used_at"),
                expires_at=key.get("expires_at"),
                created_at=key["created_at"]
            )
            for key in response.data
        ]

        return APIKeyList(keys=keys, count=len(keys))

    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreate,
    auth: AuthContext = Depends(get_current_user)
):
    """Create a new API key.

    The full key is only returned once in this response.
    Store it securely - it cannot be retrieved again.
    """
    try:
        supabase = get_supabase_admin_client()

        # Generate the key
        full_key, key_prefix, key_hash = generate_api_key()

        # Calculate expiration if specified
        expires_at: Optional[datetime] = None
        if request.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

        # Insert into database
        now = datetime.now(timezone.utc)
        insert_data = {
            "user_id": auth.user_id,
            "name": request.name,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "scopes": request.scopes,
            "is_active": True,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": now.isoformat()
        }

        response = supabase.table("api_keys").insert(insert_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create API key"
            )

        key_record = response.data[0]

        logger.info(f"Created API key {key_prefix}... for user {auth.user_id}")

        return APIKeyResponse(
            id=key_record["id"],
            name=key_record["name"],
            key=full_key,  # Only time the full key is returned
            key_prefix=key_prefix,
            scopes=key_record.get("scopes", []),
            expires_at=expires_at,
            created_at=now
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    auth: AuthContext = Depends(get_current_user)
):
    """Revoke (deactivate) an API key.

    The key is not deleted, just marked as inactive.
    This allows for auditing of previously used keys.
    """
    try:
        supabase = get_supabase_admin_client()

        # Verify the key belongs to the user
        check_response = supabase.table("api_keys").select("id").eq(
            "id", key_id
        ).eq("user_id", auth.user_id).execute()

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Deactivate the key
        supabase.table("api_keys").update({
            "is_active": False
        }).eq("id", key_id).execute()

        logger.info(f"Revoked API key {key_id} for user {auth.user_id}")

        return {"message": "API key revoked successfully", "key_id": key_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@router.delete("/{key_id}/permanent")
async def delete_api_key(
    key_id: str,
    auth: AuthContext = Depends(get_current_user)
):
    """Permanently delete an API key.

    This action cannot be undone.
    """
    try:
        supabase = get_supabase_admin_client()

        # Verify the key belongs to the user
        check_response = supabase.table("api_keys").select("id").eq(
            "id", key_id
        ).eq("user_id", auth.user_id).execute()

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Delete the key
        supabase.table("api_keys").delete().eq("id", key_id).execute()

        logger.info(f"Deleted API key {key_id} for user {auth.user_id}")

        return {"message": "API key deleted permanently", "key_id": key_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key"
        )
