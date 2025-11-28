"""Response models for API endpoints."""
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field

from .session import SessionStatus, ScrapeMode


class ScrapeResponse(BaseModel):
    """Response model for scraping endpoint."""

    session_id: str = Field(..., description="Unique session identifier")
    status: SessionStatus = Field(..., description="Current session status")
    message: str = Field(..., description="Human-readable message")
    websocket_url: Optional[str] = Field(
        None, description="WebSocket URL for real-time updates"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "20231108_140530_abc123",
                "status": "pending",
                "message": "Scraping session created successfully",
                "websocket_url": "ws://localhost:8000/ws/20231108_140530_abc123",
            }
        }


class SessionResponse(BaseModel):
    """Response model for session retrieval."""

    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    url: str
    purpose: str
    mode: ScrapeMode
    schema: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    sources: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    pages_scraped: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "20231108_140530_abc123",
                "status": "completed",
                "created_at": "2023-11-08T14:05:30",
                "updated_at": "2023-11-08T14:06:45",
                "url": "https://example.com",
                "purpose": "Extract contact information",
                "mode": "single-page",
                "schema": {"contact_email": "string", "phone": "string"},
                "extracted_data": {
                    "contact_email": "info@example.com",
                    "phone": "+1-234-567-8900",
                },
                "sources": ["https://example.com"],
            }
        }


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: List[SessionResponse]
    total: int = Field(..., description="Total number of sessions")
