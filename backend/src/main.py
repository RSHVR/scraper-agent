"""FastAPI application entry point."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set
import json
import os

from .config import settings
from .routes import scrape, sessions, gym_scrape, embed, query
from .utils.logger import logger

# Suppress tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Create FastAPI app
app = FastAPI(
    title="Scraper Agent API",
    description="AI-powered web scraping agent with intelligent data extraction",
    version="1.0.0",
    debug=settings.debug,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
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
app.include_router(gym_scrape.router)
app.include_router(sessions.router)
app.include_router(embed.router)
app.include_router(query.router)


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
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting Scraper Agent API")
    logger.info(f"Storage path: {settings.storage_path}")
    logger.info(f"Debug mode: {settings.debug}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down Scraper Agent API")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
