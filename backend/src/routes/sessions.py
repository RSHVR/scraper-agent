"""Session management API endpoints."""
from fastapi import APIRouter, HTTPException, Path
from typing import List

from ..models import SessionResponse, SessionListResponse
from ..services import session_manager
from ..services.storage_service import storage_service
from ..utils.logger import logger

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """List all scraping sessions.

    Returns:
        List of all sessions sorted by creation time (newest first)
    """
    try:
        logger.info("Listing all sessions")
        sessions = await session_manager.list_sessions()

        # Convert to response models
        session_responses = [
            SessionResponse(
                session_id=session.metadata.session_id,
                status=session.metadata.status,
                created_at=session.metadata.created_at,
                updated_at=session.metadata.updated_at,
                url=session.metadata.url,
                purpose=session.metadata.purpose,
                mode=session.metadata.mode,
                schema=session.schema,
                extracted_data=session.extracted_data,
                sources=session.sources,
                error_message=session.metadata.error_message,
                pages_scraped=storage_service.count_scraped_pages(session.metadata.session_id),
            )
            for session in sessions
        ]

        return SessionListResponse(
            sessions=session_responses, total=len(session_responses)
        )

    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str = Path(..., description="Session identifier")
) -> SessionResponse:
    """Get details of a specific session.

    Args:
        session_id: Session identifier

    Returns:
        Session details
    """
    try:
        logger.info(f"Getting session: {session_id}")
        session = await session_manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionResponse(
            session_id=session.metadata.session_id,
            status=session.metadata.status,
            created_at=session.metadata.created_at,
            updated_at=session.metadata.updated_at,
            url=session.metadata.url,
            purpose=session.metadata.purpose,
            mode=session.metadata.mode,
            schema=session.schema,
            extracted_data=session.extracted_data,
            sources=session.sources,
            error_message=session.metadata.error_message,
            pages_scraped=storage_service.count_scraped_pages(session_id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(
    session_id: str = Path(..., description="Session identifier")
) -> dict:
    """Delete a session and all its data.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    try:
        logger.info(f"Deleting session: {session_id}")
        success = await session_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"message": f"Session {session_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
