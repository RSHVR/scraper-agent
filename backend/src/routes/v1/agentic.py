"""Agentic scraping API endpoints."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, APIKeyHeader
from typing import Any, Optional
import asyncio
import json
import jwt
from jwt.exceptions import InvalidTokenError

from slowapi import Limiter
from slowapi.util import get_remote_address

from ...agents.agentic_scraper import AgenticScraper
from ...services.storage_service import StorageService
from ...models.agentic import AgenticScrapeRequest, AgentResult
from ...models.auth import AuthContext
from ...auth.dependencies import get_current_user, get_rate_limit_key
from ...auth.api_keys import validate_api_key
from ...config import settings
from ...utils.logger import logger

router = APIRouter(tags=["agentic"])

# Rate limiter for expensive endpoints - uses user_id if authenticated, IP otherwise
limiter = Limiter(key_func=get_rate_limit_key)

# Storage service for generating session IDs
storage_service = StorageService()


async def link_session_to_user(session_id: str, user_id: str) -> None:
    """Link a scrape session to the authenticated user for ownership tracking."""
    try:
        from ...auth.supabase_client import get_supabase_admin_client
        supabase = get_supabase_admin_client()

        supabase.table("session_ownership").upsert({
            "session_id": session_id,
            "user_id": user_id
        }).execute()

        logger.debug(f"Linked session {session_id} to user {user_id}")
    except Exception as e:
        # Don't fail the request if session linking fails
        logger.warning(f"Failed to link session to user: {e}")


async def authenticate_websocket(websocket: WebSocket) -> Optional[AuthContext]:
    """Authenticate a WebSocket connection using query params or first message.

    WebSocket connections can authenticate via:
    1. Query param: ?token=<jwt>
    2. Query param: ?api_key=<key>
    3. First message: {"type": "auth", "token": "<jwt>"}
    4. First message: {"type": "auth", "api_key": "<key>"}
    """
    # Check query params first
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("api_key")

    if token:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            return AuthContext(
                user_id=payload["sub"],
                method="jwt",
                email=payload.get("email"),
                scopes=["scrape:read", "scrape:write"]
            )
        except InvalidTokenError as e:
            logger.warning(f"Invalid WebSocket JWT: {e}")
            return None

    if api_key:
        key_data = await validate_api_key(api_key)
        if key_data:
            return AuthContext(
                user_id=key_data["user_id"],
                method="api_key",
                scopes=key_data["scopes"]
            )
        return None

    return None


@router.websocket("/scrape/agentic/ws")
async def agentic_scrape_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agentic scraping.

    Authentication (required):
        Query param: ?token=<jwt> or ?api_key=<key>

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
    # Authenticate before accepting the connection
    auth = await authenticate_websocket(websocket)
    if not auth:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()
    session_id = storage_service.generate_session_id()
    agent: AgenticScraper | None = None

    # Link session to authenticated user
    await link_session_to_user(session_id, auth.user_id)

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
                except Exception as e:
                    logger.warning(f"Error processing WebSocket message: {e}")
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
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def agentic_scrape_sync(
    request: Request,
    scrape_request: AgenticScrapeRequest,
    auth: AuthContext = Depends(get_current_user),
) -> AgentResult:
    """
    Non-streaming agentic scrape endpoint.

    Requires authentication via:
    - Bearer token (JWT) in Authorization header
    - API key in X-API-Key header

    For clients that don't support WebSocket.
    Returns final result only (no progress updates).

    Args:
        request: FastAPI Request object (for rate limiting)
        scrape_request: Scrape request with url, goal, provider, max_iterations
        auth: Authenticated user context

    Returns:
        AgentResult with status, data, and metrics
    """
    session_id = storage_service.generate_session_id()

    # Link session to authenticated user
    await link_session_to_user(session_id, auth.user_id)

    # Store auth in request state for rate limiting
    request.state.auth = auth

    agent = AgenticScraper(
        session_id=session_id,
        provider=scrape_request.provider,
        model=scrape_request.model,
        max_iterations=scrape_request.max_iterations
    )

    result = await agent.run(
        goal=scrape_request.goal,
        url=str(scrape_request.url) if scrape_request.url else None
    )

    return result
