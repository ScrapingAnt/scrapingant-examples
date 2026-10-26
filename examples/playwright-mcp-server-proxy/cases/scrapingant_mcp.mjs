import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

const transport = new StreamableHTTPClientTransport(new URL('https://api.scrapingant.com/mcp/'), {
  requestInit: { headers: { 'x-api-key': process.env.SCRAPINGANT_API_KEY } },
});
const client = new Client({ name: 'proxy-lab', version: '1.0.0' });
await client.connect(transport);

const { tools } = await client.listTools();
console.log('tools:', tools.map((t) => t.name).join(', '));

// The same call an agent makes: a page fetched through a residential IP in Japan
const result = await client.callTool({
  name: 'get_web_page_text',
  arguments: { url: 'https://ipinfo.io/json', browser: false, proxy_type: 'residential', proxy_country: 'JP' },
});
const exit = JSON.parse(result.content[0].text);
console.log('exit:', exit.country, exit.city);
await client.close();
