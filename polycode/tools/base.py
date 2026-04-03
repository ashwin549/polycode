from abc import ABC, abstractmethod
from dataclasses import dataclass

from polycode.providers.base import ToolDefinition


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""

    def to_str(self) -> str:
        if self.success:
            return self.output
        return f"ERROR: {self.error}"


class BaseTool(ABC):
    """All tools expose a definition (for the LLM) and a run method."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        ...

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        ...