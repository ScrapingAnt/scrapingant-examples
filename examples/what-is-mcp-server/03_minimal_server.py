"""The smallest useful MCP server: one tool that fetches a page as Markdown through ScrapingAnt.

Speaks stdio: the client launches this file as a subprocess and exchanges
newline-delimited JSON-RPC messages over stdin/stdout. Drive it with
03_client.py, or register it in Claude Code:
  claude mcp add my-scraper -- python 03_minimal_server.py
"""
import os

import requests
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("my-scraper")


@mcp.tool()
def fetch_markdown(url: str, browser: bool = True) -> str:
    """Fetch a web page and return its main content as Markdown."""
    r = requests.get("https://api.scrapingant.com/v2/markdown",
                     params={"url": url, "browser": str(browser).lower()},
                     headers={"x-api-key": os.environ.get("SCRAPINGANT_API_KEY", "")}, timeout=120)
    if r.status_code != 200:
        # Return the failure as text: the model can read it and tell the user.
        # An uncaught exception would reach the model only as "Error executing tool".
        return f"fetch failed: HTTP {r.status_code} {r.text[:200]}"
    return r.json()["markdown"]


if __name__ == "__main__":
    mcp.run()  # stdio transport
