"""
Shell tool — runs commands in an isolated Docker container.

Isolation:
  - Uses python:3.12-slim image
  - Mounts working directory READ-ONLY at /workspace
  - Network disabled (--network none)
  - Container auto-removed after each run
  - Hard timeout via threading
"""

import threading
import queue
from pathlib import Path

from polycode.providers.base import ToolDefinition
from .base import BaseTool, ToolResult

DOCKER_IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT = 60


class ShellTool(BaseTool):
    """Execute shell commands in a Docker-isolated environment."""

    def __init__(self, cwd: Path, allow_network: bool = False, timeout: int = DEFAULT_TIMEOUT):
        self.cwd = cwd
        self.allow_network = allow_network
        self.timeout = timeout
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            import docker
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="shell",
            description=(
                "Run a shell command in a secure, isolated Docker container. "
                "The working directory is mounted read-only at /workspace. "
                "Network access is disabled. Timeout: 60 seconds. "
                "Use for running tests, linters, compilers, or inspecting output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run (bash). Runs inside /workspace.",
                    },
                    "install": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional pip packages to install before running.",
                    },
                },
                "required": ["command"],
            },
        )

    def _run_container(self, client, command: str, install: list[str] | None) -> str:
        """Run container and return output. Raises on failure."""
        # Build script
        script_parts = ["cd /workspace"]
        if install:
            pkgs = " ".join(install)
            script_parts.append(f"pip install --quiet {pkgs}")
        script_parts.append(command)
        full_script = " && ".join(script_parts)

        # Convert Windows path to Docker-compatible format
        cwd_str = str(self.cwd.resolve())

        output = client.containers.run(
            image=DOCKER_IMAGE,
            command=["bash", "-c", full_script],
            volumes={
                cwd_str: {"bind": "/workspace", "mode": "ro"},
            },
            network_mode="none" if not self.allow_network else "bridge",
            remove=True,
            stdout=True,
            stderr=True,
            mem_limit="512m",
        )
        return output.decode("utf-8", errors="replace")

    def run(self, command: str, install: list[str] | None = None) -> ToolResult:
        if not self._docker_available:
            return ToolResult(
                success=False,
                output="",
                error=(
                    "Docker is not available. "
                    "Make sure Docker Desktop is running and try again."
                ),
            )

        try:
            import docker
            client = docker.from_env()

            # Pull image if not present (only downloads once, cached after)
            try:
                client.images.get(DOCKER_IMAGE)
            except docker.errors.ImageNotFound:
                client.images.pull(DOCKER_IMAGE)

            # Run in a thread so we can enforce timeout ourselves
            result_queue: queue.Queue = queue.Queue()

            def target():
                try:
                    out = self._run_container(client, command, install)
                    result_queue.put(("ok", out))
                except Exception as e:
                    result_queue.put(("err", str(e)))

            t = threading.Thread(target=target, daemon=True)
            t.start()
            t.join(timeout=self.timeout)

            if t.is_alive():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {self.timeout}s",
                )

            status, value = result_queue.get()
            if status == "ok":
                return ToolResult(success=True, output=value or "(no output)")
            else:
                return ToolResult(success=False, output="", error=value)

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))