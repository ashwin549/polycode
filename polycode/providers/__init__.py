from .base import BaseProvider, Message, ToolCall, ToolDefinition
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider


PROVIDERS: dict[str, type[BaseProvider]] = {
    "claude": AnthropicProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gpt": OpenAIProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, model: str | None = None, **kwargs) -> BaseProvider:
    """Instantiate a provider by short name (e.g. 'claude', 'openai', 'gemini', 'ollama')."""
    key = name.lower()
    cls = PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {list(PROVIDERS.keys())}")
    return cls(model=model, **kwargs)


__all__ = [
    "BaseProvider", "Message", "ToolCall", "ToolDefinition",
    "AnthropicProvider", "OpenAIProvider", "GeminiProvider", "OllamaProvider",
    "get_provider", "PROVIDERS",
]