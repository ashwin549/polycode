from polycode.providers.base import ToolDefinition
from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo (free, no API key needed)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web for current information. Returns titles, URLs, and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of results to return (default 5, max 10).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )

    def run(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            from ddgs import DDGS

            max_results = min(max_results, 10)
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        f"Title: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"Snippet: {r.get('body', '')}\n"
                    )

            if not results:
                return ToolResult(success=True, output="No results found.")
            return ToolResult(success=True, output="\n---\n".join(results))

        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="duckduckgo_search not installed. Run: pip install duckduckgo-search",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
