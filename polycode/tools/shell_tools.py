"""
Shell tool — runs commands in an isolated Docker container.

Isolation approach:
  - Uses the official python:3.12-slim image (small, has bash)
  - Mounts the working directory as READ-ONLY at /workspace inside the container
  - Mounts a temp output dir READ-WRITE at /output so commands can write files back
  - Network is DISABLED (--network none) unless explicitly enabled
  - Container is auto-removed after each run
  - Hard timeout: 60 seconds

If Docker is not available, the tool reports this and refuses to run.
"""

import os
import tempfile
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
                "Write outputs to /output if you need files back. "
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
                        "description": "Optional list of pip packages to install before running the command.",
                    },
                },
                "required": ["command"],
            },
        )

    def run(self, command: str, install: list[str] | None = None) -> ToolResult:
        if not self._docker_available:
            return ToolResult(
                success=False,
                output="",
                error=(
                    "Docker is not available on this machine. "
                    "Install Docker and ensure the daemon is running to use the shell tool."
                ),
            )

        try:
            import docker

            client = docker.from_env()

            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)

                # Build the full command
                parts = ["bash", "-c"]
                script_parts = ["cd /workspace"]
                if install:
                    pkgs = " ".join(install)
                    script_parts.append(f"pip install --quiet {pkgs}")
                script_parts.append(command)
                full_script = " && ".join(script_parts)
                parts.append(full_script)

                container_result = client.containers.run(
                    image=DOCKER_IMAGE,
                    command=parts,
                    volumes={
                        str(self.cwd.resolve()): {"bind": "/workspace", "mode": "ro"},
                        str(output_dir.resolve()): {"bind": "/output", "mode": "rw"},
                    },
                    network_mode="none" if not self.allow_network else "bridge",
                    remove=True,
                    stdout=True,
                    stderr=True,
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=50000,  # 0.5 CPUs
                    timeout=self.timeout,
                )

                output = container_result.decode("utf-8", errors="replace")

                # Check if anything was written to /output
                output_files = list(output_dir.iterdir())
                if output_files:
                    output += f"\n\n[Files written to /output: {[f.name for f in output_files]}]"

                return ToolResult(success=True, output=output or "(no output)")

        except Exception as e:
            err = str(e)
            if "timeout" in err.lower():
                return ToolResult(success=False, output="", error=f"Command timed out after {self.timeout}s")
            return ToolResult(success=False, output="", error=err)
