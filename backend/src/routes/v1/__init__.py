"""V1 API routes for agentic scraping."""

from fastapi import APIRouter

from .agentic import router as agentic_router

# V1 router that combines all v1 endpoints
router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include the agentic scraping routes
router.include_router(agentic_router)

__all__ = ["router"]
