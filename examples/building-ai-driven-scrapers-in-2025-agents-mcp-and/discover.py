"""Capture public MCP discovery only: no key, retrieval, or model calls."""
import asyncio
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with asyncio.timeout(60):
        async with streamable_http_client('https://api.scrapingant.com/mcp/') as streams:
            async with ClientSession(*streams, read_timeout_seconds=30) as session:
                initialization = await session.initialize()
                tools = await session.list_tools()
                capture = {'initialization': initialization.model_dump(mode='json', by_alias=True),
                           'tools': tools.model_dump(mode='json', by_alias=True),
                           'retrieval_calls': 0, 'model_calls': 0}
                out = Path(__file__).parent / 'expected_output' / 'discovery.json'
                out.write_text(json.dumps(capture, indent=2) + '\n')
                print(json.dumps({'protocol': initialization.protocol_version,
                                  'tools': [tool.name for tool in tools.tools],
                                  'retrieval_calls': 0, 'model_calls': 0}))

if __name__ == '__main__':
    asyncio.run(main())
