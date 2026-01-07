"""LLM Provider abstraction for Claude, Ollama, and HuggingFace."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import anthropic
import ollama
from huggingface_hub import InferenceClient

from ..config import settings
from ..utils.logger import logger


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: List[Dict], system: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return provider name for logging."""
        pass


class ClaudeProvider(LLMProvider):
    """Claude API provider."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialize Claude provider.

        Args:
            model: Model name to use
        """
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model

    def chat(self, messages: List[Dict], system: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Send chat completion request to Claude API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        logger.info(f"[LLM] Calling Claude {self.model}...")
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages
            )
            logger.info(f"[LLM] Claude {self.model} responded")
            return response.content[0].text
        except Exception as e:
            logger.error(f"[LLM] Claude {self.model} failed: {e}")
            raise

    def get_name(self) -> str:
        """Return provider name for logging."""
        return f"Claude ({self.model})"


class OllamaProvider(LLMProvider):
    """Ollama API provider (local or cloud)."""

    def __init__(self, model: str = "kimi-k2-thinking:cloud", host: Optional[str] = None):
        """Initialize Ollama provider.

        Args:
            model: Model name to use
            host: Ollama server host (defaults to settings.ollama_host)
        """
        self.model = model
        self.host = host or settings.ollama_host

        # Initialize client based on host type
        if self.host == "https://ollama.com":
            # Cloud mode - requires API key
            if not settings.ollama_api_key:
                raise ValueError("OLLAMA_API_KEY required for Ollama Cloud")
            self.client = ollama.Client(
                host=self.host,
                headers={"Authorization": f"Bearer {settings.ollama_api_key}"}
            )
            logger.info(f"[LLM] Initialized Ollama Cloud client")
        else:
            # Local mode
            self.client = ollama.Client(host=self.host)
            logger.info(f"[LLM] Initialized Ollama local client at {self.host}")

    def chat(self, messages: List[Dict], system: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Send chat completion request to Ollama API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        logger.info(f"[LLM] Calling Ollama {self.model} at {self.host}...")

        # Prepend system message if provided
        if system:
            messages = [{"role": "system", "content": system}] + messages

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={"num_predict": max_tokens}
            )
            logger.info(f"[LLM] Ollama {self.model} responded")
            return response.message.content
        except Exception as e:
            logger.error(f"[LLM] Ollama {self.model} failed: {e}")
            raise

    def get_name(self) -> str:
        """Return provider name for logging."""
        return f"Ollama ({self.model})"


class HuggingFaceProvider(LLMProvider):
    """HuggingFace Inference API provider."""

    def __init__(self, model: str, provider: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize HuggingFace provider.

        Args:
            model: Model ID (e.g., "moonshotai/Kimi-K2-Instruct")
            provider: Optional provider routing (fastest, cheapest, or provider name)
            api_key: Optional API key (defaults to settings.huggingface_api_key)
        """
        self.model = model
        self.provider = provider if provider and provider != "(none)" else None
        # Append provider suffix if specified
        self.full_model = f"{model}:{self.provider}" if self.provider else model
        token = api_key or settings.huggingface_api_key
        self.client = InferenceClient(token=token)
        logger.info(f"[LLM] Initialized HuggingFace client for {self.full_model}")

    def chat(self, messages: List[Dict], system: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Send chat completion request to HuggingFace Inference API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        logger.info(f"[LLM] Calling HuggingFace {self.full_model}...")

        # Prepend system message if provided
        if system:
            messages = [{"role": "system", "content": system}] + messages

        try:
            response = self.client.chat.completions.create(
                model=self.full_model,
                messages=messages,
                max_tokens=max_tokens
            )
            logger.info(f"[LLM] HuggingFace {self.full_model} responded")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[LLM] HuggingFace {self.full_model} failed: {e}")
            raise

    def get_name(self) -> str:
        """Return provider name for logging."""
        return f"HuggingFace ({self.full_model})"


def get_query_provider(provider_type: str = "claude") -> LLMProvider:
    """Get LLM provider for query rewriting.

    Args:
        provider_type: "claude" or "ollama"

    Returns:
        LLM provider instance
    """
    if provider_type == "ollama":
        return OllamaProvider(model=settings.ollama_model)
    else:
        return ClaudeProvider(model="claude-3-5-haiku-20241022")


def get_answer_provider(provider_type: str = "claude") -> LLMProvider:
    """Get LLM provider for answer synthesis.

    Args:
        provider_type: "claude" or "ollama"

    Returns:
        LLM provider instance
    """
    if provider_type == "ollama":
        return OllamaProvider(model=settings.ollama_model)
    else:
        return ClaudeProvider(model="claude-sonnet-4-20250514")
