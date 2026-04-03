import os
from typing import Iterator

from google import genai
from google.genai import types

from .base import BaseProvider, Message, ToolCall, ToolDefinition


class GeminiProvider(BaseProvider):
    """Wraps the Google Gemini API."""

    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        super().__init__(model or self.DEFAULT_MODEL)
        self.client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])

    # ── format helpers ────────────────────────────────────────────────────────

    def _to_gemini_contents(self, messages: list[Message]) -> list[types.Content]:
        contents = []
        for m in messages:
            if m.role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m.content)]))

            elif m.role == "assistant":
                parts = []
                if m.content:
                    parts.append(types.Part(text=m.content))
                for tc in m.tool_calls:
                    parts.append(types.Part(
                        function_call=types.FunctionCall(name=tc.name, args=tc.arguments)
                    ))
                contents.append(types.Content(role="model", parts=parts))

            elif m.role == "tool":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=m.tool_name or "",
                            response={"result": m.content},
                        )
                    )],
                ))
        return contents

    def _to_gemini_tools(self, tools: list[ToolDefinition]) -> list[types.Tool] | None:
        if not tools:
            return None
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def _parse_response(self, response) -> Message:
        text = ""
        tool_calls = []
        import uuid
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text = part.text
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4()),
                    name=fc.name,
                    arguments=dict(fc.args),
                ))
        return Message(role="assistant", content=text, tool_calls=tool_calls)

    # ── public interface ──────────────────────────────────────────────────────

    def chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Message:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=self._to_gemini_tools(tools),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=self._to_gemini_contents(messages),
            config=config,
        )
        return self._parse_response(response)

    def stream_chat(self, messages: list[Message], tools: list[ToolDefinition], system: str = "") -> Iterator[str]:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=self._to_gemini_tools(tools),
        )
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=self._to_gemini_contents(messages),
            config=config,
        ):
            if chunk.text:
                yield chunk.text
