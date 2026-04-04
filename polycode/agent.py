"""
The agent loop.

Flow:
  1. User sends a message
  2. Agent calls the LLM with the full conversation + tool definitions
  3. If the LLM returns tool calls → execute them, append results, go to 2
  4. If the LLM returns text only → yield the text and stop

This module is UI-agnostic: the CLI layer (cli.py) handles all display.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from polycode.providers.base import BaseProvider, Message, ToolDefinition
from polycode.tools.base import BaseTool
from polycode.safe_edit import reset_snapshot_session


SYSTEM_PROMPT = """You are Polycode, a highly capable AI coding assistant.

You have access to tools that let you read and write files, edit code, search the web, and run commands in an isolated environment.

Guidelines:
- Before editing a file, read it first to understand the current content.
- Use edit_file for targeted changes (prefer it over write_file for existing files).
- When making code changes, explain what you're doing and why.
- Use web_search for documentation, library versions, or anything you're unsure about.
- Use shell to run tests, linters, or verify your changes actually work.
- Be concise but thorough. Show diffs when relevant.
- If something could go wrong, warn the user before proceeding.
"""


@dataclass
class AgentState:
    history: list[Message] = field(default_factory=list)
    tool_calls_made: int = 0
    max_tool_calls: int = 50  # safety limit per turn


class Agent:
    def __init__(
        self,
        provider: BaseProvider,
        tools: list[BaseTool],
        cwd: Path,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_tool_end: Callable[[str, str, bool], None] | None = None,
    ):
        self.provider = provider
        self.tools: dict[str, BaseTool] = {t.definition.name: t for t in tools}
        self.tool_definitions: list[ToolDefinition] = [t.definition for t in tools]
        self.cwd = cwd
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.state = AgentState()

    def chat(self, user_message: str) -> Iterator[str]:
        """
        Process a user message and yield text tokens.
        Tool calls are handled transparently; their results are not yielded
        (the CLI callbacks handle display).
        """
        self.state.history.append(Message(role="user", content=user_message))
        self.state.tool_calls_made = 0
        reset_snapshot_session()  # each turn gets its own snapshot group

        while True:
            if self.state.tool_calls_made >= self.state.max_tool_calls:
                yield "\n⚠️ Tool call limit reached. Stopping."
                break

            response = self.provider.chat(
                messages=self.state.history,
                tools=self.tool_definitions,
                system=SYSTEM_PROMPT,
            )

            self.state.history.append(response)

            # Yield any text content
            if response.content:
                yield response.content

            # No tool calls → we're done
            if not response.tool_calls:
                break

            # Execute each tool call
            for tc in response.tool_calls:
                self.state.tool_calls_made += 1

                if self.on_tool_start:
                    self.on_tool_start(tc.name, tc.arguments)

                tool = self.tools.get(tc.name)
                if tool is None:
                    result_str = f"Unknown tool: {tc.name}"
                    success = False
                else:
                    try:
                        result = tool.run(**tc.arguments)
                        result_str = result.to_str()
                        success = result.success
                    except Exception as e:
                        result_str = f"Tool error: {e}"
                        success = False

                if self.on_tool_end:
                    self.on_tool_end(tc.name, result_str, success)

                # Append tool result to history
                self.state.history.append(Message(
                    role="tool",
                    content=result_str,
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                ))

    def reset(self):
        """Clear conversation history."""
        self.state = AgentState()