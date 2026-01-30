"""Services for the application."""
from .storage_service import StorageService, storage_service
from .session_manager import SessionManager, session_manager
from .http_client import HTTPClient, fetch_url
# Migrated to Cohere embed-v4.0 + rerank-v4.0-fast for API-based embeddings
from .vector_service_cohere import VectorServiceCohere, vector_service
# LLM provider abstraction for Claude and Ollama
from .llm_provider import (
    LLMProvider,
    ClaudeProvider,
    OllamaProvider,
    get_query_provider,
    get_answer_provider,
)
# Trafilatura-based content extraction
from .trafilatura_service import TrafilaturaService, trafilatura_service

__all__ = [
    "StorageService",
    "storage_service",
    "SessionManager",
    "session_manager",
    "HTTPClient",
    "fetch_url",
    "VectorServiceCohere",
    "vector_service",
    "LLMProvider",
    "ClaudeProvider",
    "OllamaProvider",
    "get_query_provider",
    "get_answer_provider",
    "TrafilaturaService",
    "trafilatura_service",
]
