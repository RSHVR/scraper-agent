"""Scraping API endpoints."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any

from ..models import ScrapeRequest, ScrapeResponse, SessionStatus
from ..agents import orchestrator
from ..utils.logger import logger
from ..services.storage_service import storage_service

router = APIRouter(prefix="/api", tags=["scrape"])


@router.post("/scrape", response_model=ScrapeResponse)
async def create_scrape_session(
    request: ScrapeRequest, background_tasks: BackgroundTasks
) -> ScrapeResponse:
    """Create a new scraping session.

    Args:
        request: Scraping request with URL, purpose, optional schema, and mode
        background_tasks: FastAPI background tasks

    Returns:
        Scrape response with session ID and status
    """
    try:
        logger.info(f"Creating scrape session for URL: {request.url}")

        # Create session immediately to get a real session_id
        session_id = storage_service.generate_session_id()

        # Create session directory
        storage_service.create_session_directory(session_id)

        # Create initial metadata
        from ..models import SessionMetadata
        from datetime import datetime
        metadata = SessionMetadata(
            session_id=session_id,
            status=SessionStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url=str(request.url),
            purpose=request.purpose or "",
            mode=request.mode,
        )
        storage_service.save_metadata(session_id, metadata)

        # Start the scraping process in the background with the session_id
        background_tasks.add_task(execute_scrape_task, request, session_id)

        return ScrapeResponse(
            session_id=session_id,
            status=SessionStatus.PENDING,
            message="Scraping session created successfully. Processing in background.",
            websocket_url=f"ws://localhost:8000/ws/{session_id}",
        )

    except Exception as e:
        logger.error(f"Error creating scrape session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_scrape_task(request: ScrapeRequest, session_id: str) -> None:
    """Execute the scraping task in the background using the orchestrator.

    Phase 1 only: Sitemap-based raw HTML scraping (NO Claude, NO schema generation).
    The orchestrator handles session creation and the full workflow.

    Args:
        request: Scraping request
        session_id: Pre-generated session ID
    """
    try:
        logger.info(f"Starting background scrape task for {request.url} with session {session_id}")

        # Call the orchestrator to execute Phase 1 scraping with the pre-created session_id
        # Pass the session_id to orchestrator so it uses this instead of creating a new one
        result_session_id, success = await orchestrator.execute_scrape(request, session_id=session_id)

        if success:
            logger.info(f"Scrape completed successfully: {result_session_id}")
        else:
            logger.error(f"Scrape failed: {result_session_id}")

    except Exception as e:
        logger.error(f"Error in background scrape task: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: str) -> Dict[str, Any]:
    """Get the status of a scraping session.

    Args:
        session_id: The session identifier

    Returns:
        Session status information including progress
    """
    try:
        # Load session metadata
        metadata = storage_service.load_metadata(session_id)

        if not metadata:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Count pages scraped
        pages_scraped = storage_service.count_scraped_pages(session_id)

        # Return status in format expected by frontend
        return {
            "session_id": session_id,
            "status": metadata.status.value,
            "pages_scraped": pages_scraped,
            "url": metadata.url,
            "created_at": metadata.created_at.isoformat() if metadata.created_at else None,
            "updated_at": metadata.updated_at.isoformat() if metadata.updated_at else None,
            "error_message": metadata.error_message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
