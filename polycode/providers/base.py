"""
Common types and base class for all LLM providers.

All providers translate to/from this internal format:

  User message:    Message(role="user", content="text")
  Assistant text:  Message(role="assistant", content="text")
  Tool call:       Message(role="assistant", content="text", tool_calls=[ToolCall(...)])
  Tool result:     Message(role="tool", content="result", tool_call_id="...", tool_name="...")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # only for role="tool"
    tool_name: str | None = None     # only for role="tool"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema object


class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str = "",
    ) -> Message:
        """Send a full conversation and return the assistant's reply."""
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str = "",
    ) -> Iterator[str]:
        """Yield text tokens as they arrive. Tool calls are handled internally."""
        ...
