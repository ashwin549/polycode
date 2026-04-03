"""
Ollama provider — reuses OpenAIProvider since Ollama exposes an OpenAI-compatible API.
Just point base_url at the local Ollama server.
"""

from .openai_provider import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """Local Ollama models via the OpenAI-compatible endpoint."""

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        super().__init__(
            model=model or self.DEFAULT_MODEL,
            api_key="ollama",  # Ollama ignores the key but OpenAI client needs one
            base_url=base_url or self.DEFAULT_BASE_URL,
        )
