"""FastAPI authentication dependencies."""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from ..config import settings
from ..models.auth import AuthContext
from ..utils.logger import logger
from .api_keys import validate_api_key


# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
) -> AuthContext:
    """Validate JWT or API key and return user context.

    This dependency requires authentication - use get_optional_user
    for endpoints where auth is optional.

    Args:
        bearer_token: JWT from Authorization header
        api_key: API key from X-API-Key header

    Returns:
        AuthContext with user information

    Raises:
        HTTPException: If not authenticated or token is invalid
    """
    # Try JWT first (if provided)
    if bearer_token:
        try:
            payload = jwt.decode(
                bearer_token.credentials,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )

            return AuthContext(
                user_id=payload["sub"],
                method="jwt",
                email=payload.get("email"),
                scopes=["scrape:read", "scrape:write"]  # JWT users get full access
            )

        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Try API key (if provided)
    if api_key:
        key_data = await validate_api_key(api_key)
        if key_data:
            return AuthContext(
                user_id=key_data["user_id"],
                method="api_key",
                scopes=key_data["scopes"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )

    # No valid authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    bearer_token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_header),
) -> Optional[AuthContext]:
    """Get user context if authenticated, None otherwise.

    Use this for endpoints where authentication is optional.
    """
    if not bearer_token and not api_key:
        return None

    try:
        return await get_current_user(bearer_token, api_key)
    except HTTPException:
        return None


def require_auth(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    """Alias for get_current_user - use for clarity in route definitions."""
    return auth


def require_scope(required_scope: str):
    """Dependency factory to require a specific scope.

    Usage:
        @router.post("/scrape")
        async def create_scrape(auth: AuthContext = Depends(require_scope("scrape:write"))):
            ...
    """
    async def scope_checker(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if required_scope not in auth.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}"
            )
        return auth

    return scope_checker


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on authentication.

    Rate limits by user_id if authenticated, otherwise by IP.
    This enables more generous limits for authenticated users.
    """
    auth: Optional[AuthContext] = getattr(request.state, "auth", None)
    if auth:
        return f"user:{auth.user_id}"

    # Fall back to IP-based limiting
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"
