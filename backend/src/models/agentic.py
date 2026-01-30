"""Models for agentic scraping."""

from pydantic import BaseModel, HttpUrl
from typing import Any, Optional, Literal
from datetime import datetime


class AgentCostMetrics(BaseModel):
    """Cost and usage tracking for agent runs."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0
    total_cost_usd: float = 0.0
    provider: str = ""
    model: str = ""


class AgentResult(BaseModel):
    """Result of an agent run."""
    status: Literal["success", "failed", "cancelled", "max_iterations", "completed"]
    data: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    reason: Optional[str] = None
    suggestion: Optional[str] = None
    iterations: int = 0
    metrics: Optional[AgentCostMetrics] = None


class AgenticScrapeRequest(BaseModel):
    """Request to start an agentic scrape."""
    url: Optional[HttpUrl] = None  # Optional - agent can discover URLs via web_search
    goal: str
    max_iterations: int = 20
    provider: str = "claude"  # "claude", "cohere", "ollama", "huggingface"
    model: Optional[str] = None  # Override default model


class AgentMessage(BaseModel):
    """WebSocket message from agent."""
    type: Literal["iteration", "thought", "tool_call", "tool_result", "complete", "error", "session_started", "cancel_ack"]
    session_id: Optional[str] = None
    iteration: Optional[int] = None
    max_iterations: Optional[int] = None
    timestamp: Optional[datetime] = None

    # Type-specific fields
    text: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_id: Optional[str] = None
    success: Optional[bool] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    result: Optional[AgentResult] = None

    model_config = {"extra": "allow"}

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now()
        super().__init__(**data)
