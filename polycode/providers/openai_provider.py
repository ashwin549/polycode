import json
import os
from typing import Iterator

from openai import OpenAI

from .base import BaseProvider, Message, ToolCall, ToolDefinition


class OpenAIProvider(BaseProvider):
    """Wraps the OpenAI API (GPT-4o and friends)."""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        super().__init__(model or self.DEFAULT_MODEL)
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            base_url=base_url,
        )

    # ── format helpers ────────────────────────────────────────────────────────

    def _to_oai_messages(self, messages: list[Message], system: str) -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            if m.role == "user":
                result.append({"role": "user", "content": m.content})

            elif m.role == "assistant":
                msg: dict = {"role": "assistant", "content": m.content or None}
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in m.tool_calls
                    ]
                result.append(msg)

            elif m.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content,
                })
        return result

    def _to_oai_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def _parse_response(self, response) -> Message:
        choice = response.choices[0].message
        text = choice.content or ""
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))
        return Message(role="assistant", content=text, tool_calls=tool_calls)

    # ── public interface ──────────────────────────────────────────────────────

    def chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Message:
        kwargs = dict(
            model=self.model,
            messages=self._to_oai_messages(messages, system),
        )
        if tools:
            kwargs["tools"] = self._to_oai_tools(tools)
            kwargs["tool_choice"] = "auto"
        response = self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    def stream_chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Iterator[str]:
        # Streaming with tool calls is complex; stream text only, tools via non-streaming
        kwargs = dict(
            model=self.model,
            messages=self._to_oai_messages(messages, system),
            stream=True,
        )
        if tools:
            kwargs["tools"] = self._to_oai_tools(tools)
        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
