"""Data models for the application."""
from .requests import ScrapeRequest
from .responses import ScrapeResponse, SessionResponse, SessionListResponse
from .session import (
    Session,
    SessionMetadata,
    SessionStatus,
    ScrapeMode,
)
from .agentic import (
    AgentCostMetrics,
    AgentResult,
    AgenticScrapeRequest,
    AgentMessage,
)
from .auth import (
    AuthContext,
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    RefreshRequest,
    UserProfile,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyInfo,
    APIKeyList,
)

__all__ = [
    "ScrapeRequest",
    "ScrapeResponse",
    "SessionResponse",
    "SessionListResponse",
    "Session",
    "SessionMetadata",
    "SessionStatus",
    "ScrapeMode",
    "AgentCostMetrics",
    "AgentResult",
    "AgenticScrapeRequest",
    "AgentMessage",
    # Auth models
    "AuthContext",
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "RefreshRequest",
    "UserProfile",
    "APIKeyCreate",
    "APIKeyResponse",
    "APIKeyInfo",
    "APIKeyList",
]
