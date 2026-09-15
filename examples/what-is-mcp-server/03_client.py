"""Launch 03_minimal_server.py over stdio, list its tools, and call one (call needs SCRAPINGANT_API_KEY)."""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["03_minimal_server.py"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.server_info.name}, protocol {init.protocol_version}")
            tools = await session.list_tools()
            for t in tools.tools:
                print(f"tool: {t.name} - {t.description}  params={list(t.input_schema['properties'])}")
            if not os.environ.get("SCRAPINGANT_API_KEY"):
                print("tools/call skipped (SCRAPINGANT_API_KEY not set)")
                return
            result = await session.call_tool("fetch_markdown", {"url": "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"})
            if result.is_error:
                print("fetch_markdown FAILED (isError=true):", result.content[0].text.strip()[:160])
            else:
                print("fetch_markdown ->", result.content[0].text.strip()[:120])


asyncio.run(main())
