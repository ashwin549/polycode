import os
from typing import Iterator

import anthropic

from .base import BaseProvider, Message, ToolCall, ToolDefinition


class AnthropicProvider(BaseProvider):
    """Wraps the Anthropic API (Claude models)."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        super().__init__(model or self.DEFAULT_MODEL)
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    # ── format helpers ────────────────────────────────────────────────────────

    def _to_anthropic_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            if m.role == "user":
                result.append({"role": "user", "content": m.content})

            elif m.role == "assistant":
                if m.tool_calls:
                    content: list[dict] = []
                    if m.content:
                        content.append({"type": "text", "text": m.content})
                    for tc in m.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                    result.append({"role": "assistant", "content": content})
                else:
                    result.append({"role": "assistant", "content": m.content})

            elif m.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }],
                })
        return result

    def _to_anthropic_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _parse_response(self, response) -> Message:
        text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return Message(role="assistant", content=text, tool_calls=tool_calls)

    # ── public interface ──────────────────────────────────────────────────────

    def chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Message:
        kwargs = dict(
            model=self.model,
            max_tokens=8096,
            messages=self._to_anthropic_messages(messages),
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)
        response = self.client.messages.create(**kwargs)
        return self._parse_response(response)

    def stream_chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Iterator[str]:
        kwargs = dict(
            model=self.model,
            max_tokens=8096,
            messages=self._to_anthropic_messages(messages),
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)
        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
