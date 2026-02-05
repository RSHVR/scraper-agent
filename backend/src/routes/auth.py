"""Authentication routes proxying to Supabase Auth."""

from fastapi import APIRouter, HTTPException, status, Depends, Response
from supabase_auth.errors import AuthApiError

from ..auth.supabase_client import get_supabase_client
from ..auth.dependencies import get_current_user
from ..models.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    RefreshRequest,
    UserProfile,
    AuthContext,
)
from ..utils.logger import logger

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new user with email and password.

    Supabase will send a confirmation email if email confirmation is enabled.
    """
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
        })

        if not response.session:
            # Email confirmation may be required
            return AuthResponse(
                access_token="",
                refresh_token="",
                expires_in=0,
                user={"email": request.email, "email_confirmed": False}
            )

        return AuthResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "email_confirmed": response.user.email_confirmed_at is not None
            }
        )

    except AuthApiError as e:
        logger.warning(f"Registration failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })

        return AuthResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "email_confirmed": response.user.email_confirmed_at is not None
            }
        )

    except AuthApiError as e:
        logger.warning(f"Login failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout")
async def logout(auth: AuthContext = Depends(get_current_user)):
    """Logout and invalidate the current session."""
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Still return success - client should clear tokens regardless
        return {"message": "Logged out"}


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        supabase = get_supabase_client()
        response = supabase.auth.refresh_session(request.refresh_token)

        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        return AuthResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in,
        )

    except AuthApiError as e:
        logger.warning(f"Token refresh failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(auth: AuthContext = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    try:
        supabase = get_supabase_client()
        # Use admin client to fetch user details
        from ..auth.supabase_client import get_supabase_admin_client
        admin = get_supabase_admin_client()

        response = admin.auth.admin.get_user_by_id(auth.user_id)

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return UserProfile(
            id=response.user.id,
            email=response.user.email,
            email_confirmed_at=response.user.email_confirmed_at,
            created_at=response.user.created_at,
            updated_at=response.user.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile"
        )


@router.post("/password/reset")
async def request_password_reset(email: str):
    """Request a password reset email."""
    try:
        supabase = get_supabase_client()
        supabase.auth.reset_password_email(email)
        # Always return success to prevent email enumeration
        return {"message": "If an account exists, a password reset email has been sent"}

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        # Still return success to prevent enumeration
        return {"message": "If an account exists, a password reset email has been sent"}


@router.get("/oauth/{provider}")
async def initiate_oauth(provider: str):
    """Get OAuth URL for the specified provider.

    Supported providers: google, github
    The client should redirect the user to the returned URL.
    """
    supported_providers = ["google", "github"]
    if provider not in supported_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider. Supported: {', '.join(supported_providers)}"
        )

    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {
                "redirect_to": f"{supabase.supabase_url}/auth/v1/callback"
            }
        })

        return {"url": response.url, "provider": provider}

    except Exception as e:
        logger.error(f"OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate OAuth"
        )
