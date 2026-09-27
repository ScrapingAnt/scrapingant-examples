import http from 'node:http';

// The app reads its preference once at startup. Later writes do not rerender rows.
const CATALOG_HTML = `<!doctype html><html lang="en"><meta charset="utf-8">
<title>Synthetic localStorage catalog</title><link rel="icon" href="data:,">
<table><thead><tr><th>SKU</th><th>Currency</th><th>Price</th></tr></thead><tbody></tbody></table>
<script>
(async () => {
  const fromQuery = new URL(location.href).searchParams.get('region');
  const fromStorage = localStorage.getItem('region');
  const region = fromQuery || fromStorage || 'US';
  const source = fromQuery ? 'query' : fromStorage ? 'localStorage' : 'default';
  const response = await fetch('/api/catalog?region=' + encodeURIComponent(region));
  const result = await response.json();
  window.catalogObservation = { startup_region: region, startup_source: source,
    target_status: response.status, response_region: result.region };
  for (const record of result.records) {
    const row = document.createElement('tr');
    for (const field of ['sku', 'currency', 'price']) {
      const cell = document.createElement('td'); cell.textContent = record[field]; row.appendChild(cell);
    }
    document.querySelector('tbody').appendChild(row);
  }
  document.body.dataset.ready = 'yes';
})().catch(error => { document.body.dataset.error = error.message; });
</script></html>`;

export async function startFixture() {
  let catalogRequests = 0;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    if (url.pathname === '/api/catalog') {
      catalogRequests += 1;
      const region = url.searchParams.get('region') === 'EU' ? 'EU' : 'US';
      const currency = region === 'EU' ? 'EUR' : 'USD';
      const multiplier = region === 'EU' ? 0.9 : 1;
      const source = [['SKU-101', 900], ['SKU-202', 1800], ['SKU-303', 2700], ['SKU-404', 3600]];
      const records = source.map(([sku, cents]) => ({ sku, currency, price: (cents * multiplier / 100).toFixed(2) }));
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify({ region, records }));
    } else if (url.pathname === '/catalog' || url.pathname === '/blank') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      res.end(url.pathname === '/catalog' ? CATALOG_HTML : '<!doctype html><title>Fixture blank</title><body>Fixture blank</body>');
    } else {
      res.writeHead(404); res.end('Not found');
    }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  return {
    origin: `http://127.0.0.1:${server.address().port}`,
    get catalogRequests() { return catalogRequests; },
    async close() {
      server.closeAllConnections();
      await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
    },
  };
}

export async function requestJSON(address) {
  const url = new URL(address);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password) {
    throw new Error('This fixture helper permits HTTP loopback only');
  }
  return new Promise((resolve, reject) => {
    const request = http.get(url, { agent: false }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => {
        try { resolve({ status: response.statusCode, body: JSON.parse(Buffer.concat(chunks).toString('utf8')) }); }
        catch (error) { reject(error); }
      });
      response.on('error', reject);
    });
    request.setTimeout(5000, () => request.destroy(new Error('Fixture response timed out')));
    request.on('error', reject);
  });
}
