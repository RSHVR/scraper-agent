"""Authentication models for Supabase Auth and API keys."""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field


class AuthContext(BaseModel):
    """Authenticated user context available in request handlers."""

    user_id: str = Field(..., description="Supabase user ID (UUID)")
    method: Literal["jwt", "api_key"] = Field(..., description="Authentication method used")
    scopes: List[str] = Field(default=["scrape:read", "scrape:write"], description="Permission scopes")
    email: Optional[str] = Field(default=None, description="User email (if available)")


# Auth Request/Response Models

class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Authentication response with tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: Optional[dict] = None


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class UserProfile(BaseModel):
    """User profile information."""

    id: str
    email: str
    email_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# API Key Models

class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the key")
    scopes: List[str] = Field(
        default=["scrape:read", "scrape:write"],
        description="Permission scopes for this key"
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiration (optional)"
    )


class APIKeyResponse(BaseModel):
    """Response after creating an API key (includes full key - shown only once)."""

    id: str
    name: str
    key: str = Field(..., description="Full API key - save this, it won't be shown again!")
    key_prefix: str = Field(..., description="Key prefix for identification")
    scopes: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime


class APIKeyInfo(BaseModel):
    """API key information (without the full key)."""

    id: str
    name: str
    key_prefix: str = Field(..., description="First 12 characters of the key")
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class APIKeyList(BaseModel):
    """List of user's API keys."""

    keys: List[APIKeyInfo]
    count: int
