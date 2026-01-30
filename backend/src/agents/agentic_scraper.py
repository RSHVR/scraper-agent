"""LangGraph ReAct agent implementation for intelligent web scraping."""

import json
from typing import Any, Callable, Optional
from datetime import datetime

from langgraph.prebuilt import create_react_agent

from .tools import get_tools, set_tool_context, ToolContext
from .llm_factory import get_llm, TokenTracker, calculate_cost
from .rag_tool import create_rag_tool, create_embed_tool
from .prompts import SCRAPER_SYSTEM_PROMPT
from ..services.vector_service_cohere import VectorServiceCohere
from ..services.html_cleaner import HTMLCleaner
from ..models.agentic import AgentCostMetrics, AgentResult
from ..utils.logger import logger


class AgenticScraper:
    """
    LangGraph ReAct agent for intelligent web scraping.

    Uses LangGraph's create_react_agent with native tool calling for reliable
    tool execution without hallucination issues.
    """

    def __init__(
        self,
        session_id: str,
        provider: str = "claude",
        model: Optional[str] = None,
        max_iterations: int = 20
    ):
        """
        Initialize the agentic scraper.

        Args:
            session_id: Unique session identifier
            provider: LLM provider ("claude", "ollama", "huggingface")
            model: Optional model override
            max_iterations: Maximum number of tool-calling iterations
        """
        self.session_id = session_id
        self.max_iterations = max_iterations
        self.provider = provider
        self.model = model

        # Token tracking callback
        self.token_tracker = TokenTracker()

        # LLM instance (via LangChain)
        self.llm = get_llm(provider, model, callbacks=[self.token_tracker])

        # Tool context (shared state across tools)
        self.tool_context = ToolContext(session_id)
        set_tool_context(self.tool_context)

        # Initialize services for RAG tools
        self.vector_service = VectorServiceCohere()
        self.html_cleaner = HTMLCleaner()

        # Cost tracking
        self.metrics = AgentCostMetrics(provider=provider, model=model or "")

        # Cancellation
        self._cancelled = False

    def _build_tools(self) -> list:
        """Build all tools for the agent."""
        # Core scraping tools
        tools = get_tools()

        # LlamaIndex RAG tool for searching knowledge base
        rag_tool = create_rag_tool(self.vector_service)
        tools.append(rag_tool)

        # Embed tool for storing content
        embed_tool = create_embed_tool(self.vector_service, self.html_cleaner)
        tools.append(embed_tool)

        return tools

    def _build_agent(self, tools: list):
        """
        Create agent based on model capabilities.

        For most models, LangGraph's create_react_agent uses native JSON tool calling.
        For llama3-groq-tool-use, we use a custom XML-based agent that matches
        the model's training format.
        """
        # Models that require XML tool format instead of JSON
        XML_TOOL_MODELS = ["llama3-groq-tool-use"]

        # Check if this model needs XML format
        model_name = self.model or ""
        needs_xml = self.provider == "ollama" and any(
            xml_model in model_name for xml_model in XML_TOOL_MODELS
        )

        if needs_xml:
            logger.info(f"Using XMLToolAgent for model: {model_name}")
            from .xml_agent import XMLToolAgent
            return XMLToolAgent(
                llm=self.llm,
                tools=tools,
                max_iterations=self.max_iterations,
                metrics=self.metrics
            )
        else:
            # Use LangGraph for Claude and other JSON-capable models
            logger.info(f"Using LangGraph ReAct agent for provider: {self.provider}")
            return create_react_agent(
                model=self.llm,
                tools=tools,
                prompt=SCRAPER_SYSTEM_PROMPT
            )

    def _parse_output(self, output: Any) -> Any:
        """Parse tool output, handling JSON strings."""
        if isinstance(output, str):
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"raw": output}
        return output

    def _is_xml_agent(self, agent) -> bool:
        """Check if agent is an XMLToolAgent (has direct run method)."""
        from .xml_agent import XMLToolAgent
        return isinstance(agent, XMLToolAgent)

    async def run(
        self,
        goal: str,
        url: Optional[str] = None,
        on_message: Optional[Callable[[dict], Any]] = None
    ) -> AgentResult:
        """
        Execute the agent until goal is achieved or max iterations.

        Automatically routes to XMLToolAgent.run() for XML-format models
        or LangGraph's astream_events for JSON-capable models.

        Args:
            goal: What the user wants to achieve
            url: Optional starting URL (if None, agent uses web_search to discover)
            on_message: Async callback for streaming progress (for WebSocket)

        Returns:
            AgentResult with status, data, and metrics
        """
        # Build tools and agent
        tools = self._build_tools()
        agent = self._build_agent(tools)

        try:
            # XMLToolAgent has its own run method that handles everything
            if self._is_xml_agent(agent):
                logger.info(f"Running XMLToolAgent for goal: {goal}")
                result = await agent.run(goal, url, on_message)
                # Update metrics from XML agent
                self.metrics = result.metrics or self.metrics
                return result

            # LangGraph agent uses streaming events
            return await self._run_langgraph_agent(agent, goal, url, on_message)

        finally:
            # Cleanup browser contexts
            await self._cleanup()

    async def _run_langgraph_agent(
        self,
        agent,
        goal: str,
        url: Optional[str] = None,
        on_message: Optional[Callable[[dict], Any]] = None
    ) -> AgentResult:
        """
        Execute LangGraph agent with streaming events.

        This handles Claude and other JSON-based tool-calling models.
        """
        # Build prompt based on whether URL is provided
        if url:
            prompt_content = (
                f"Goal: {goal}\n\n"
                f"Starting URL: {url}\n\n"
                "Analyze this URL and achieve the goal step by step."
            )
        else:
            prompt_content = (
                f"Goal: {goal}\n\n"
                "No starting URL provided. Use web_search to discover relevant URLs, "
                "then scrape and extract the information needed to achieve the goal."
            )

        # LangGraph uses messages-based input
        input_messages = {
            "messages": [{
                "role": "user",
                "content": prompt_content
            }]
        }

        iteration = 0

        try:
            logger.info(f"Starting LangGraph agent execution for goal: {goal}")

            # Stream events from the LangGraph agent
            # Set high recursion limit to allow many tool calls
            config = {"recursion_limit": 100}
            async for event in agent.astream_events(input_messages, version="v2", config=config):
                # Check cancellation
                if self._cancelled:
                    return AgentResult(
                        status="cancelled",
                        iterations=iteration,
                        metrics=self._build_metrics()
                    )

                event_type = event.get("event")
                event_name = event.get("name", "")

                # Debug logging
                logger.debug(f"Event: {event_type}, name: {event_name}")

                # Handle tool start (equivalent to on_agent_action)
                if event_type == "on_tool_start":
                    iteration += 1
                    tool_input = event.get("data", {}).get("input", {})

                    # LOG TOOL CALLS
                    try:
                        args_str = json.dumps(tool_input)[:500]
                    except (TypeError, ValueError):
                        args_str = str(tool_input)[:500]
                    logger.info(f"Tool call [{iteration}]: {event_name} with args: {args_str}")

                    if on_message:
                        await on_message({
                            "type": "tool_call",
                            "tool_name": event_name,
                            "tool_input": tool_input,
                            "iteration": iteration,
                            "timestamp": datetime.now().isoformat()
                        })

                # Handle tool completion
                elif event_type == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    parsed_output = self._parse_output(output)

                    # LOG TOOL RESULTS
                    try:
                        result_preview = json.dumps(parsed_output)[:300] if parsed_output else "None"
                    except (TypeError, ValueError):
                        result_preview = str(parsed_output)[:300]
                    logger.info(f"Tool result [{iteration}]: {event_name} -> {result_preview}")

                    if on_message:
                        await on_message({
                            "type": "tool_result",
                            "tool_name": event_name,
                            "data": parsed_output,
                            "iteration": iteration,
                            "timestamp": datetime.now().isoformat()
                        })

                    # Check for terminal tool results
                    if isinstance(parsed_output, dict) and parsed_output.get("terminal"):
                        if parsed_output.get("saved"):
                            return AgentResult(
                                status="success",
                                data=parsed_output,
                                iterations=iteration,
                                metrics=self._build_metrics()
                            )
                        elif parsed_output.get("status") == "failed":
                            return AgentResult(
                                status="failed",
                                reason=parsed_output.get("reason"),
                                suggestion=parsed_output.get("suggestion"),
                                iterations=iteration,
                                metrics=self._build_metrics()
                            )

                # Handle LLM streaming (agent reasoning)
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if on_message and chunk:
                        content = getattr(chunk, "content", None)
                        if content and isinstance(content, str):
                            await on_message({
                                "type": "thought",
                                "text": content[:500],
                                "iteration": iteration,
                                "timestamp": datetime.now().isoformat()
                            })

                # Handle LLM completion
                elif event_type == "on_chat_model_end":
                    if on_message:
                        output = event.get("data", {}).get("output")
                        if output:
                            content = getattr(output, "content", None)
                            if content and isinstance(content, str):
                                await on_message({
                                    "type": "thought",
                                    "text": content[:500],
                                    "iteration": iteration,
                                    "timestamp": datetime.now().isoformat()
                                })

                # Handle chain completion (agent finished)
                elif event_type == "on_chain_end":
                    # Check if this is the top-level agent completion
                    if event_name == "LangGraph":
                        output = event.get("data", {}).get("output", {})
                        messages = output.get("messages", [])

                        if messages:
                            # Get the last message as the final output
                            last_msg = messages[-1]
                            final_content = getattr(last_msg, "content", str(last_msg))

                            logger.info(f"Agent completed with output: {final_content[:200]}...")

                            return AgentResult(
                                status="completed",
                                message=final_content if isinstance(final_content, str) else str(final_content),
                                iterations=iteration,
                                metrics=self._build_metrics()
                            )

                # Check iteration limit
                if iteration >= self.max_iterations:
                    logger.warning(f"Max iterations ({self.max_iterations}) reached")
                    return AgentResult(
                        status="max_iterations",
                        iterations=iteration,
                        metrics=self._build_metrics()
                    )

            # If we get here, agent completed normally
            return AgentResult(
                status="completed",
                iterations=iteration,
                metrics=self._build_metrics()
            )

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            return AgentResult(
                status="failed",
                reason=str(e),
                iterations=iteration,
                metrics=self._build_metrics()
            )

    async def cancel(self):
        """Request cancellation of the current run."""
        self._cancelled = True

    async def _cleanup(self):
        """Cleanup resources - kill browser session when agent completes."""
        try:
            # Always try to cleanup the session associated with this agent
            await self.tool_context.browser.kill_session(self.session_id)
            logger.info(f"Cleaned up browser session: {self.session_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup browser session: {e}")

    def _build_metrics(self) -> AgentCostMetrics:
        """Build cost metrics from token tracker."""
        self.metrics.total_input_tokens = self.token_tracker.total_input_tokens
        self.metrics.total_output_tokens = self.token_tracker.total_output_tokens
        self.metrics.total_llm_calls = self.token_tracker.total_calls
        self.metrics.total_cost_usd = calculate_cost(
            self.provider,
            self.metrics.total_input_tokens,
            self.metrics.total_output_tokens
        )
        return self.metrics
