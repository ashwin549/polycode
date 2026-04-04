"""
Diff-based editing tool.

The model calls edit_file with:
  - path: file to edit
  - old_str: exact string to find (must appear exactly once)
  - new_str: replacement string

Before applying, the agent shows the diff to the user and asks for confirmation.
"""

import difflib
from pathlib import Path

from polycode.providers.base import ToolDefinition
from polycode.safe_edit import snapshot_file, stage_edit, apply_staged, reset_snapshot_session
from .base import BaseTool, ToolResult


def _safe_path(path: str, cwd: Path) -> Path:
    resolved = (cwd / path).resolve()
    if not str(resolved).startswith(str(cwd.resolve())):
        raise ValueError(f"Path '{path}' escapes the working directory.")
    return resolved


def make_diff(path: str, original: str, modified: str) -> str:
    """Return a unified diff string between original and modified."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "\n".join(diff)


class EditFileTool(BaseTool):
    """str_replace-style targeted edits with diff preview."""

    def __init__(self, cwd: Path, confirm_callback=None, dry_run: bool = False):
        self.cwd = cwd
        self.confirm_callback = confirm_callback
        self.dry_run = dry_run

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description=(
                "Edit a file by replacing an exact unique string with new content. "
                "The old_str must appear EXACTLY ONCE in the file. "
                "Use read_file first if you are unsure about the exact content. "
                "The user will be shown a diff and asked to confirm before the change is applied."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to edit, relative to the working directory.",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Exact string to find and replace. Must be unique in the file.",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement string.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this change is being made.",
                    },
                },
                "required": ["path", "old_str", "new_str"],
            },
        )

    def run(self, path: str, old_str: str, new_str: str, reason: str = "") -> ToolResult:
        try:
            p = _safe_path(path, self.cwd)

            if not p.exists():
                return ToolResult(success=False, output="", error=f"File not found: {path}")

            original = p.read_text(encoding="utf-8")
            count = original.count(old_str)

            if count == 0:
                return ToolResult(success=False, output="", error=f"old_str not found in {path}")
            if count > 1:
                return ToolResult(success=False, output="", error=(
                    f"old_str appears {count} times in {path}. Make it more specific so it's unique."
                ))

            modified = original.replace(old_str, new_str, 1)
            diff = make_diff(path, original, modified)

            # 1. Snapshot original (enables undo)
            snapshot_file(self.cwd, path)

            # 2. Write modified to staging (real file still untouched)
            stage_edit(self.cwd, path, modified)

            # 3. Dry-run: stop here, never apply
            if self.dry_run:
                return ToolResult(
                    success=True,
                    output=f"[DRY RUN] Staged but not applied: {path}\n\n{diff}",
                )

            # 4. Ask user for approval
            if self.confirm_callback:
                approved = self.confirm_callback(path, diff, reason)
                if not approved:
                    return ToolResult(success=False, output="", error="Edit rejected by user.")

            # 5. Apply: move staged file over the real file
            apply_staged(self.cwd, path)
            return ToolResult(success=True, output=f"Edit applied to {path}.\n\n{diff}")

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))