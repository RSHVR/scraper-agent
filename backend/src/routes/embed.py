"""Embedding API endpoints."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional
from pydantic import BaseModel

from ..services import storage_service, vector_service
from ..utils.logger import logger

router = APIRouter(prefix="/api", tags=["embed"])


class EmbedRequest(BaseModel):
    """Request model for embedding."""

    session_id: Optional[str] = None
    filename: Optional[str] = None


class EmbedResponse(BaseModel):
    """Response model for embedding."""

    status: str
    message: str
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None


@router.post("/embed", response_model=EmbedResponse)
async def create_embed_task(
    request: EmbedRequest, background_tasks: BackgroundTasks
) -> EmbedResponse:
    """Create a new embedding task.

    Args:
        request: Embedding request with session_id or filename
        background_tasks: FastAPI background tasks

    Returns:
        Embed response with status
    """
    try:
        # Determine which file to embed
        if request.session_id:
            # Find the markdown file for this session
            files = storage_service.list_raw_html_files()
            matching_files = [f for f in files if request.session_id in f]

            if not matching_files:
                raise HTTPException(
                    status_code=404,
                    detail=f"No markdown file found for session {request.session_id}"
                )

            filename = matching_files[0]
            logger.info(f"Found markdown file for session {request.session_id}: {filename}")

        elif request.filename:
            filename = request.filename
            logger.info(f"Embedding specific file: {filename}")

        else:
            raise HTTPException(
                status_code=400,
                detail="Either session_id or filename must be provided"
            )

        # Start the embedding process in the background
        background_tasks.add_task(execute_embed_task, filename)

        return EmbedResponse(
            status="pending",
            message=f"Embedding task started for {filename}. Processing in background.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating embed task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_embed_task(filename: str) -> None:
    """Execute the embedding task in the background.

    Args:
        filename: Name of the markdown file to embed
    """
    try:
        logger.info(f"Starting background embed task for {filename}")

        # Load cleaned markdown data
        data = storage_service.load_raw_html(filename)
        if not data:
            logger.error(f"Failed to load file: {filename}")
            return

        domain = data.get("website", "unknown")
        gym_name = data.get("gym_name", "Unknown Gym")
        pages = data.get("pages", [])

        if not pages:
            logger.warning(f"No pages found in {filename}")
            return

        # Initialize vector service and load model
        logger.info("Loading BGE-M3 embedding model...")
        vector_service.load_model()
        logger.info("Model loaded successfully")

        # Create collection
        vector_service.create_collection()

        # Process each page
        total_chunks = 0
        for page_idx, page in enumerate(pages):
            page_name = page.get("page_name", "Unknown Page")
            page_url = page.get("page_url", "")
            markdown_content = page.get("markdown_content", "")

            if not markdown_content:
                logger.warning(f"Skipping empty page: {page_name}")
                continue

            # Chunk the markdown
            chunks = vector_service.chunk_markdown(markdown_content, page_name)

            if not chunks:
                logger.warning(f"No chunks extracted from {page_name}")
                continue

            # Insert chunks into Milvus
            vector_service.insert_chunks(
                domain=domain,
                gym_name=gym_name,
                page_name=page_name,
                page_url=page_url,
                chunks=chunks,
            )

            total_chunks += len(chunks)
            logger.info(f"Embedded page {page_idx + 1}/{len(pages)}: {page_name} ({len(chunks)} chunks)")

        logger.info(f"Embedding completed: {len(pages)} pages, {total_chunks} total chunks")

    except Exception as e:
        logger.error(f"Error in background embed task: {str(e)}")
