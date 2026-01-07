"""Application configuration management."""
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API Configuration
    anthropic_api_key: str = ""  # Required - set via ANTHROPIC_API_KEY env var

    # Cohere API Configuration
    cohere_api_key: str = ""  # Required - set via COHERE_API_KEY env var

    # HuggingFace Configuration
    huggingface_api_key: str = ""  # Set via HUGGINGFACE_API_KEY env var

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"  # Local Ollama by default
    ollama_api_key: str = ""  # Only needed for Ollama Cloud
    ollama_model: str = "kimi-k2:1t-cloud"

    # LLM Provider Selection ("claude" or "ollama")
    llm_provider: str = "claude"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Storage Configuration
    storage_base_path: str = "/tmp/data" if os.getenv("SPACE_ID") else "./data"

    # Agent Configuration
    max_parallel_extractions: int = 3
    default_timeout: int = 30
    browser_timeout: int = 60  # Playwright page load timeout in seconds

    # Model Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def storage_path(self) -> Path:
        """Get the resolved storage path."""
        return Path(self.storage_base_path).expanduser().resolve()


# Global settings instance
settings = Settings()
