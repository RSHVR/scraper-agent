"""FastAPI application entry point."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Set
import json
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .routes import scrape, sessions, embed, query, auth, keys
from .routes.v1 import router as v1_router
from .auth.dependencies import get_rate_limit_key
from .utils.logger import logger

# Suppress tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Rate limiter setup - uses user_id if authenticated, IP otherwise
limiter = Limiter(key_func=get_rate_limit_key)

# Create FastAPI app
app = FastAPI(
    title="Scraper Agent API",
    description="AI-powered web scraping agent with intelligent data extraction",
    version="1.0.0",
    debug=settings.debug,
)

# Add rate limiter to app state
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Please try again later."}
    )

# Configure CORS with explicit origins (not wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    """Manager for WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect a WebSocket client.

        Args:
            websocket: WebSocket connection
            session_id: Session identifier
        """
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Disconnect a WebSocket client.

        Args:
            websocket: WebSocket connection
            session_id: Session identifier
        """
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_message(self, session_id: str, message: dict):
        """Send message to all clients connected to a session.

        Args:
            session_id: Session identifier
            message: Message to send
        """
        if session_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    disconnected.add(connection)

            # Clean up disconnected clients
            for connection in disconnected:
                self.active_connections[session_id].discard(connection)


manager = ConnectionManager()


# Include routers
app.include_router(scrape.router)
app.include_router(sessions.router)
app.include_router(embed.router)
app.include_router(query.router)

# Authentication routes
app.include_router(auth.router)
app.include_router(keys.router)

# V1 API routes (agentic scraping)
app.include_router(v1_router)


# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time session updates.

    Args:
        websocket: WebSocket connection
        session_id: Session identifier
    """
    await manager.connect(websocket, session_id)

    try:
        # Send initial connection message
        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session_id,
                "message": "WebSocket connected",
            }
        )

        # Keep connection alive and listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                # Echo back or handle client messages if needed
                await websocket.send_json(
                    {"type": "echo", "data": data, "session_id": session_id}
                )
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        manager.disconnect(websocket, session_id)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "scraper-agent"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "Scraper Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "auth": {
            "register": "/api/auth/register",
            "login": "/api/auth/login",
            "me": "/api/auth/me",
        },
        "api_keys": "/api/keys",
        "agentic_api": "/api/v1/scrape/agentic",
        "agentic_ws": "/api/v1/scrape/agentic/ws",
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting Scraper Agent API")
    logger.info(f"Storage path: {settings.storage_path}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.cors_origins}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown with proper cleanup."""
    logger.info("Shutting down Scraper Agent API")

    # Cleanup browser sessions
    try:
        from .services.browser_client import BrowserClient
        await BrowserClient.shutdown()
        logger.info("Browser sessions cleaned up")
    except Exception as e:
        logger.warning(f"Error during browser cleanup: {e}")

    logger.info("Shutdown complete")


# Readiness check endpoint
@app.get("/health/ready")
async def readiness_check():
    """Check if service is ready to accept traffic.

    Validates:
    - ChromaDB connectivity
    - LLM provider configuration

    Returns:
        Health status with individual check results
    """
    checks = {}

    # Check ChromaDB
    try:
        from .services.vector_service_cohere import VectorServiceCohere
        vs = VectorServiceCohere()
        vs._connect()
        vs.collection = vs.client.get_or_create_collection("health_check")
        vs.collection.count()
        checks["chromadb"] = "ok"
    except Exception as e:
        checks["chromadb"] = f"error: {str(e)}"

    # Check if at least one LLM provider is configured
    has_llm_key = any([
        settings.anthropic_api_key,
        settings.cohere_api_key,
        settings.huggingface_api_key
    ])
    checks["llm_configured"] = "ok" if has_llm_key else "warning: no API keys"

    # Determine overall status
    has_error = any(v.startswith("error") for v in checks.values())
    all_ok = all(v == "ok" for v in checks.values())

    if has_error:
        status = "unhealthy"
        http_status = 503
    elif all_ok:
        status = "ready"
        http_status = 200
    else:
        status = "degraded"
        http_status = 200  # Degraded is still usable

    return JSONResponse(
        status_code=http_status,
        content={"status": status, "checks": checks}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
