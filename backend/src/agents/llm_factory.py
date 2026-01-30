"""LangChain LLM factory for multi-provider support."""

from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler
from typing import Optional, Any
from ..config import settings


class TokenTracker(BaseCallbackHandler):
    """Callback to track token usage across providers."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0

    def on_llm_end(self, response: Any, **kwargs) -> None:
        self.total_calls += 1
        if hasattr(response, 'llm_output') and response.llm_output:
            usage = response.llm_output.get('token_usage', {})
            self.total_input_tokens += usage.get('prompt_tokens', 0)
            self.total_output_tokens += usage.get('completion_tokens', 0)


def get_llm(
    provider: str,
    model: Optional[str] = None,
    callbacks: Optional[list[BaseCallbackHandler]] = None
) -> BaseChatModel:
    """
    Factory function to create LLM instances for different providers.

    Args:
        provider: "claude", "cohere", "ollama", or "huggingface"
        model: Optional model override
        callbacks: Optional callbacks (e.g., TokenTracker)

    Returns:
        LangChain ChatModel instance
    """
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            max_tokens=4096,
            callbacks=callbacks
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model or settings.ollama_model or "llama3.1:70b",
            base_url=settings.ollama_host,
            callbacks=callbacks
        )

    elif provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        llm = HuggingFaceEndpoint(
            repo_id=model or "meta-llama/Llama-3.1-70B-Instruct",
            huggingfacehub_api_token=settings.huggingface_api_key,
            max_new_tokens=4096
        )
        return ChatHuggingFace(llm=llm, callbacks=callbacks)

    elif provider == "cohere":
        from langchain_cohere import ChatCohere
        return ChatCohere(
            model=model or "command-a-03-2025",
            cohere_api_key=settings.cohere_api_key,
            max_tokens=4096,
            temperature=0.3,  # Deterministic for agent behavior
            callbacks=callbacks
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")


# Cost per 1M tokens (approximate, for tracking)
COST_PER_1M_TOKENS = {
    "claude": {"input": 3.0, "output": 15.0},    # Claude Sonnet 4
    "cohere": {"input": 2.5, "output": 10.0},    # Command A
    "ollama": {"input": 0.0, "output": 0.0},     # Local/free
    "huggingface": {"input": 0.5, "output": 1.5} # HF Inference API
}


def calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD."""
    rates = COST_PER_1M_TOKENS.get(provider, {"input": 0, "output": 0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
