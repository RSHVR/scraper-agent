"""Session-related data models."""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeMode(str, Enum):
    """Scraping mode enumeration."""

    SINGLE_PAGE = "single-page"
    WHOLE_SITE = "whole-site"


class SessionMetadata(BaseModel):
    """Metadata for a scraping session."""

    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    url: str
    purpose: str
    mode: ScrapeMode
    error_message: Optional[str] = None
    total_pages: Optional[int] = None
    pages_scraped: Optional[int] = 0


class Session(BaseModel):
    """Complete session data."""

    metadata: SessionMetadata
    request_data: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    sources: List[str] = Field(default_factory=list)
