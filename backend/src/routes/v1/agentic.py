"""Agentic scraping API endpoints."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
import asyncio
import json

from ...agents.agentic_scraper import AgenticScraper
from ...services.storage_service import StorageService
from ...models.agentic import AgenticScrapeRequest, AgentResult
from ...utils.logger import logger

router = APIRouter(tags=["agentic"])

# Storage service for generating session IDs
storage_service = StorageService()


@router.websocket("/scrape/agentic/ws")
async def agentic_scrape_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agentic scraping.

    Client sends:
        {"url": "...", "goal": "...", "provider": "claude", "max_iterations": 20}

    Server streams:
        {"type": "session_started", "session_id": "..."}
        {"type": "iteration", "iteration": 1, ...}
        {"type": "thought", "text": "...", ...}
        {"type": "tool_call", "tool_name": "...", ...}
        {"type": "tool_result", "success": true, ...}
        {"type": "complete", "result": {...}}

    Client can send:
        {"type": "cancel"}
    """
    await websocket.accept()
    session_id = storage_service.generate_session_id()
    agent: AgenticScraper | None = None

    try:
        # Receive initial request
        data = await websocket.receive_json()
        request = AgenticScrapeRequest(**data)

        logger.info(f"Starting agentic scrape: session={session_id}, goal={request.goal}")

        # Send session ID
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id
        })

        # Create agent
        agent = AgenticScraper(
            session_id=session_id,
            provider=request.provider,
            model=request.model,
            max_iterations=request.max_iterations
        )

        # Message callback to forward to WebSocket
        async def on_message(msg: dict):
            msg["session_id"] = session_id
            try:
                await websocket.send_json(msg)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")

        # Listen for cancel messages in background
        async def listen_for_cancel():
            while True:
                try:
                    msg = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=0.5
                    )
                    if msg.get("type") == "cancel":
                        logger.info(f"Cancel requested for session {session_id}")
                        await agent.cancel()
                        await websocket.send_json({
                            "type": "cancel_ack",
                            "session_id": session_id
                        })
                        break
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    break
                except Exception:
                    continue

        # Run agent with cancel listener
        cancel_task = asyncio.create_task(listen_for_cancel())

        try:
            result = await agent.run(
                goal=request.goal,
                url=str(request.url) if request.url else None,
                on_message=on_message
            )

            # Send final result
            await websocket.send_json({
                "type": "complete",
                "session_id": session_id,
                "result": result.model_dump()
            })

        finally:
            cancel_task.cancel()
            try:
                await cancel_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Error in agentic scrape: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/scrape/agentic")
async def agentic_scrape_sync(request: AgenticScrapeRequest) -> AgentResult:
    """
    Non-streaming agentic scrape endpoint.

    For clients that don't support WebSocket.
    Returns final result only (no progress updates).

    Args:
        request: Scrape request with url, goal, provider, max_iterations

    Returns:
        AgentResult with status, data, and metrics
    """
    session_id = storage_service.generate_session_id()

    agent = AgenticScraper(
        session_id=session_id,
        provider=request.provider,
        model=request.model,
        max_iterations=request.max_iterations
    )

    result = await agent.run(
        goal=request.goal,
        url=str(request.url) if request.url else None
    )

    return result
