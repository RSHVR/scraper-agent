"""Session manager for tracking session lifecycle."""
from datetime import datetime
from typing import Dict, Optional, List
import asyncio

from ..models import (
    Session,
    SessionMetadata,
    SessionStatus,
    ScrapeMode,
    ScrapeRequest,
)
from .storage_service import StorageService, storage_service


class SessionManager:
    """Manager for session lifecycle and state tracking."""

    def __init__(self, storage: Optional[StorageService] = None):
        """Initialize the session manager.

        Args:
            storage: Storage service instance. Defaults to global storage_service
        """
        self.storage = storage or storage_service
        # In-memory session tracking for quick status checks
        self._active_sessions: Dict[str, SessionMetadata] = {}
        self._lock = asyncio.Lock()

    async def initialize_session(
        self, request: ScrapeRequest
    ) -> tuple[str, SessionMetadata]:
        """Initialize a new scraping session.

        Args:
            request: The scraping request

        Returns:
            Tuple of (session_id, session_metadata)
        """
        async with self._lock:
            # Generate session ID
            session_id = self.storage.generate_session_id()

            # Create session metadata
            now = datetime.now()
            metadata = SessionMetadata(
                session_id=session_id,
                status=SessionStatus.PENDING,
                created_at=now,
                updated_at=now,
                url=str(request.url),
                purpose=request.purpose,
                mode=request.mode,
            )

            # Create session directory
            self.storage.create_session_directory(session_id)

            # Save metadata and request data
            self.storage.save_metadata(session_id, metadata)
            self.storage.save_request_data(
                session_id, request.model_dump(mode="json")
            )

            # Track in memory
            self._active_sessions[session_id] = metadata

            return session_id, metadata

    async def update_status(
        self,
        session_id: str,
        status: SessionStatus,
        error_message: Optional[str] = None,
    ) -> SessionMetadata:
        """Update session status.

        Args:
            session_id: The session identifier
            status: New status
            error_message: Optional error message if status is FAILED

        Returns:
            Updated session metadata
        """
        async with self._lock:
            # Load current metadata
            metadata = self.storage.load_metadata(session_id)
            if not metadata:
                raise ValueError(f"Session {session_id} not found")

            # Update metadata
            metadata.status = status
            metadata.updated_at = datetime.now()
            if error_message:
                metadata.error_message = error_message

            # Save updated metadata
            self.storage.save_metadata(session_id, metadata)

            # Update in-memory tracking
            self._active_sessions[session_id] = metadata

            return metadata

    async def update_progress(
        self,
        session_id: str,
        total_pages: Optional[int] = None,
        pages_scraped: Optional[int] = None,
    ) -> None:
        """Update scraping progress in session metadata.

        Args:
            session_id: The session identifier
            total_pages: Total number of pages to scrape (set once after URL discovery)
            pages_scraped: Current count of pages scraped (updated incrementally)
        """
        metadata = self.storage.load_metadata(session_id)
        if not metadata:
            return

        if total_pages is not None:
            metadata.total_pages = total_pages

        if pages_scraped is not None:
            metadata.pages_scraped = pages_scraped

        metadata.updated_at = datetime.now()
        self.storage.save_metadata(session_id, metadata)

        # Update in-memory tracking
        self._active_sessions[session_id] = metadata

    async def save_schema(self, session_id: str, schema: Dict) -> None:
        """Save schema for a session.

        Args:
            session_id: The session identifier
            schema: The generated schema
        """
        self.storage.save_schema(session_id, schema)

    async def save_extracted_data(self, session_id: str, data: Dict) -> None:
        """Save extracted data for a session.

        Args:
            session_id: The session identifier
            data: The extracted data
        """
        self.storage.save_extracted_data(session_id, data)

    async def save_sources(self, session_id: str, sources: List[str]) -> None:
        """Save sources for a session.

        Args:
            session_id: The session identifier
            sources: List of source URLs
        """
        self.storage.save_json(session_id, "sources.json", {"sources": sources})

    async def save_raw_html(self, session_id: str, pages_data: List[Dict]) -> None:
        """Save raw HTML data for scraped pages.

        Args:
            session_id: The session identifier
            pages_data: List of dicts with 'page_url' and 'raw_html' keys
        """
        self.storage.save_raw_html(session_id, pages_data)

    async def save_markdown(self, session_id: str, markdown_data: List[Dict]) -> None:
        """Save markdown data for scraped pages.

        Args:
            session_id: The session identifier
            markdown_data: List of dicts with 'page_url', 'page_name', and 'markdown_content' keys
        """
        self.storage.save_markdown(session_id, markdown_data)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get complete session data.

        Args:
            session_id: The session identifier

        Returns:
            Complete session data or None if not found
        """
        return self.storage.load_session(session_id)

    async def get_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """Get session metadata.

        Args:
            session_id: The session identifier

        Returns:
            Session metadata or None if not found
        """
        # Try in-memory first
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        # Fall back to storage
        return self.storage.load_metadata(session_id)

    async def list_sessions(self) -> List[Session]:
        """List all sessions.

        Returns:
            List of all sessions sorted by creation time (newest first)
        """
        session_ids = self.storage.list_sessions()
        sessions = []

        for session_id in session_ids:
            session = self.storage.load_session(session_id)
            if session:
                sessions.append(session)

        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session identifier

        Returns:
            True if deleted successfully, False if session didn't exist
        """
        async with self._lock:
            # Remove from in-memory tracking
            self._active_sessions.pop(session_id, None)

            # Delete from storage
            return self.storage.delete_session(session_id)

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: The session identifier

        Returns:
            True if session exists, False otherwise
        """
        return self.storage.session_exists(session_id)

    async def cleanup_completed_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up completed sessions older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours for completed sessions

        Returns:
            Number of sessions deleted
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        deleted_count = 0

        sessions = await self.list_sessions()
        for session in sessions:
            if (
                session.metadata.status == SessionStatus.COMPLETED
                and session.metadata.updated_at < cutoff_time
            ):
                if await self.delete_session(session.metadata.session_id):
                    deleted_count += 1

        return deleted_count


# Global session manager instance
session_manager = SessionManager()
