import os
from pathlib import Path

from polycode.providers.base import ToolDefinition
from .base import BaseTool, ToolResult


def _safe_path(path: str, cwd: Path) -> Path:
    """Resolve path relative to cwd; reject traversal outside cwd."""
    resolved = (cwd / path).resolve()
    if not str(resolved).startswith(str(cwd.resolve())):
        raise ValueError(f"Path '{path}' escapes the working directory.")
    return resolved


class ReadFileTool(BaseTool):
    def __init__(self, cwd: Path):
        self.cwd = cwd

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the contents of a file. Returns the file content with line numbers.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file, relative to the working directory."},
                },
                "required": ["path"],
            },
        )

    def run(self, path: str) -> ToolResult:
        try:
            p = _safe_path(path, self.cwd)
            content = p.read_text(encoding="utf-8")
            numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(content.splitlines()))
            return ToolResult(success=True, output=f"File: {path}\n\n{numbered}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(BaseTool):
    def __init__(self, cwd: Path):
        self.cwd = cwd

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write content to a file, creating it (and any parent directories) if it doesn't exist. Overwrites existing content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file, relative to the working directory."},
                    "content": {"type": "string", "description": "Full content to write to the file."},
                },
                "required": ["path", "content"],
            },
        )

    def run(self, path: str, content: str) -> ToolResult:
        try:
            p = _safe_path(path, self.cwd)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            lines = content.count("\n") + 1
            return ToolResult(success=True, output=f"Wrote {lines} lines to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListFilesTool(BaseTool):
    def __init__(self, cwd: Path):
        self.cwd = cwd

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_files",
            description="List files and directories in a directory. Respects .gitignore patterns if present.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path relative to working directory. Defaults to '.' (root)."},
                    "recursive": {"type": "boolean", "description": "If true, list recursively. Default false."},
                },
                "required": [],
            },
        )

    def run(self, path: str = ".", recursive: bool = False) -> ToolResult:
        try:
            p = _safe_path(path, self.cwd)
            if not p.is_dir():
                return ToolResult(success=False, output="", error=f"'{path}' is not a directory")
            entries = []
            if recursive:
                for item in sorted(p.rglob("*")):
                    rel = item.relative_to(self.cwd)
                    suffix = "/" if item.is_dir() else ""
                    entries.append(str(rel) + suffix)
            else:
                for item in sorted(p.iterdir()):
                    rel = item.relative_to(self.cwd)
                    suffix = "/" if item.is_dir() else ""
                    entries.append(str(rel) + suffix)
            return ToolResult(success=True, output="\n".join(entries) or "(empty directory)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
