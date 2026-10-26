// Starts Playwright MCP with the given CLI flags, asks it to open a page and
// prints the page's echo of the X-Lab-Proxy header (or the error it got).
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport, getDefaultEnvironment } from '@modelcontextprotocol/sdk/client/stdio.js';

const [url, ...flags] = process.argv.slice(2);
const transport = new StdioClientTransport({
  command: 'node',
  args: ['node_modules/@playwright/mcp/cli.js', '--headless', '--isolated', '--snapshot-mode', 'none', ...flags],
  // like the "env" block of an MCP client config: only PLAYWRIGHT_MCP_* is passed on
  env: { ...getDefaultEnvironment(), ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k.startsWith('PLAYWRIGHT_MCP_'))) },
  stderr: 'ignore',
});
const client = new Client({ name: 'proxy-lab', version: '1.0.0' });
await client.connect(transport);
const result = await client.callTool({ name: 'browser_navigate', arguments: { url } });
let text = result.content.map((c) => c.text ?? '').join('\n');
if (!result.isError) {
  const body = await client.callTool({ name: 'browser_evaluate', arguments: { function: '() => document.body.innerText' } });
  text = body.content.map((c) => c.text ?? '').join('\n');
}
const via = text.match(/X-Lab-Proxy[\\"]*:\s*[\\"]*([\w-]+)/i);
const error = text.match(/net::ERR_[A-Z_]+|Proxy Authentication Required/);
console.log(via ? `X-Lab-Proxy: ${via[1]}` : error ? error[0] : 'no X-Lab-Proxy header (direct)');
await client.close();
