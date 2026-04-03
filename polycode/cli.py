"""
Polycode CLI — the interactive REPL.

Usage:
  polycode                          # uses Claude by default
  polycode --provider openai        # GPT-4o
  polycode --provider gemini        # Gemini 2.0 Flash
  polycode --provider ollama        # local Ollama
  polycode --provider ollama --model llama3.2
  polycode --provider openai --model o4-mini
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich import print as rprint

from polycode.agent import Agent
from polycode.providers import get_provider
from polycode.tools import build_tools

load_dotenv()

console = Console()
HISTORY_FILE = Path.home() / ".polycode_history"

PROVIDER_COLORS = {
    "claude": "cyan",
    "anthropic": "cyan",
    "openai": "green",
    "gpt": "green",
    "gemini": "yellow",
    "google": "yellow",
    "ollama": "magenta",
}

BANNER = """
[bold cyan]╔═══════════════════════════╗[/]
[bold cyan]║   polycode  v0.1.0        ║[/]
[bold cyan]╚═══════════════════════════╝[/]
[dim]Multi-model coding agent[/]
[dim]Type [bold]/help[/] for commands, [bold]/quit[/] to exit[/]
"""


def confirm_edit(path: str, diff: str, reason: str) -> bool:
    """Show diff and ask user to approve before applying an edit."""
    console.print()
    if reason:
        console.print(f"[bold yellow]Edit reason:[/] {reason}")
    console.print(f"[bold]Proposed changes to[/] [cyan]{path}[/]:")
    console.print(Syntax(diff, "diff", theme="monokai", line_numbers=False))
    try:
        answer = console.input("[bold]Apply this edit? [/][dim](y/N)[/] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def on_tool_start(name: str, args: dict):
    arg_summary = ", ".join(
        f"{k}={repr(v)[:60]}" for k, v in args.items() if k != "content"
    )
    console.print(f"\n[dim]-> [bold]{name}[/]({arg_summary})[/]")


def on_tool_end(name: str, result: str, success: bool):
    icon = "OK" if success else "FAIL"
    color = "green" if success else "red"
    preview = result[:200].replace("\n", " ") + ("..." if len(result) > 200 else "")
    console.print(f"[{color}]{icon}[/] [dim]{preview}[/]")


def run_repl(agent: Agent, provider_name: str, model: str):
    color = PROVIDER_COLORS.get(provider_name.lower(), "white")
    session: PromptSession = PromptSession(history=FileHistory(str(HISTORY_FILE)))

    console.print(BANNER)
    console.print(f"[{color}]Provider:[/] {provider_name}  [dim]Model:[/] {model}")
    console.print(f"[dim]Working directory:[/] {Path.cwd()}\n")

    while True:
        try:
            user_input = session.prompt("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/]")
            break

        if not user_input:
            continue

        # Built-in slash commands
        if user_input.startswith("/"):
            cmd = user_input.lstrip("/").lower()
            if cmd in ("quit", "exit", "q"):
                console.print("[dim]Bye![/]")
                break
            elif cmd == "help":
                console.print(Panel(
                    "[bold]/help[/]  — show this message\n"
                    "[bold]/clear[/] — clear conversation history\n"
                    "[bold]/cwd[/]   — show working directory\n"
                    "[bold]/quit[/]  — exit",
                    title="Commands",
                    border_style="dim",
                ))
            elif cmd == "clear":
                agent.reset()
                console.print("[dim]History cleared.[/]")
            elif cmd == "cwd":
                console.print(f"[cyan]{Path.cwd()}[/]")
            else:
                console.print(f"[red]Unknown command: {user_input}[/]")
            continue

        # Send to agent
        console.print(f"\n[{color}]agent[/] ", end="")
        try:
            full_response = ""
            for chunk in agent.chat(user_input):
                console.print(chunk, end="")
                full_response += chunk
            console.print()  # newline after response
        except KeyboardInterrupt:
            console.print("\n[dim](interrupted)[/]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/]")


def main():
    parser = argparse.ArgumentParser(
        prog="polycode",
        description="Multi-model coding agent (Claude, GPT-4o, Gemini, Ollama)",
    )
    parser.add_argument(
        "--provider", "-p",
        default=os.environ.get("POLYCODE_PROVIDER", "claude"),
        choices=["claude", "anthropic", "openai", "gpt", "gemini", "google", "ollama"],
        help="LLM provider to use (default: claude)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name (overrides provider default)",
    )
    parser.add_argument(
        "--no-shell",
        action="store_true",
        help="Disable the Docker shell tool",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Working directory for file operations (default: current dir)",
    )
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        console.print(f"[red]Working directory does not exist: {cwd}[/]")
        sys.exit(1)

    try:
        provider = get_provider(args.provider, model=args.model)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to initialize provider: {e}[/]")
        console.print("[dim]Check your API key environment variables.[/]")
        sys.exit(1)

    tools = build_tools(
        cwd=cwd,
        confirm_callback=confirm_edit,
        enable_shell=not args.no_shell,
    )

    agent = Agent(
        provider=provider,
        tools=tools,
        cwd=cwd,
        on_tool_start=on_tool_start,
        on_tool_end=on_tool_end,
    )

    run_repl(agent, provider_name=args.provider, model=provider.model)


if __name__ == "__main__":
    main()
