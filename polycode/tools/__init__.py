from pathlib import Path

from .base import BaseTool, ToolResult
from .file_tools import ReadFileTool, WriteFileTool, ListFilesTool
from .edit_tools import EditFileTool
from .search_tools import WebSearchTool
from .shell_tools import ShellTool


def build_tools(cwd: Path, confirm_callback=None, enable_shell: bool = True, dry_run: bool = False) -> list[BaseTool]:
    """Return all tools wired up for the given working directory."""
    tools: list[BaseTool] = [
        ReadFileTool(cwd),
        WriteFileTool(cwd),
        ListFilesTool(cwd),
        EditFileTool(cwd, confirm_callback=confirm_callback, dry_run=dry_run),
        WebSearchTool(),
    ]
    if enable_shell:
        tools.append(ShellTool(cwd))
    return tools


__all__ = [
    "BaseTool", "ToolResult",
    "ReadFileTool", "WriteFileTool", "ListFilesTool",
    "EditFileTool", "WebSearchTool", "ShellTool",
    "build_tools",
]