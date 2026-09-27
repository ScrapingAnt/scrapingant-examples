// Complete local-only example: install state before app scripts, then restore it.
import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { startFixture } from './fixture.mjs';
import { captureSnapshot, encodeSnapshot, decodeSnapshot, installSnapshot, scoreRecords } from './state.mjs';
import { launchBrowser, environment, navigateCatalog } from './browser_helpers.mjs';

const fixture = await startFixture();
const temporary = await mkdtemp(join(tmpdir(), 'synthetic-puppeteer-quickstart-'));
const stateFile = join(temporary, 'storage.json');
let browser, result;
try {
  browser = await launchBrowser();
  const source = await browser.createBrowserContext();
  const page = await source.newPage();
  await installSnapshot(page, { origin: fixture.origin, entries: [['region', 'EU']] }, fixture.origin);
  await page.goto(fixture.origin + '/blank');
  await writeFile(stateFile, encodeSnapshot(await captureSnapshot(page)), { mode: 0o600 });
  await source.close();

  const restoredContext = await browser.createBrowserContext();
  const restored = await restoredContext.newPage();
  const snapshot = decodeSnapshot(await readFile(stateFile, 'utf8'), fixture.origin);
  await installSnapshot(restored, snapshot, fixture.origin);
  const restoredData = await navigateCatalog(restored, fixture);

  // This fixture also exposes an explicit region URL; it does not write storage.
  const queryContext = await browser.createBrowserContext();
  const queryPage = await queryContext.newPage();
  const queryData = await navigateCatalog(queryPage, fixture, '/catalog?region=EU');
  result = {
    environment: await environment(browser),
    restored: { ...restoredData, ...scoreRecords(restoredData.records) },
    query_url: { ...queryData, ...scoreRecords(queryData.records) },
  };
  assert.equal(result.restored.exact_match, true);
  assert.equal(result.query_url.exact_match, true);
  assert.equal(result.query_url.storage_length, 0);
} finally {
  try { if (browser) await browser.close(); }
  finally { await fixture.close(); await rm(temporary, { recursive: true, force: true }); }
}
result.temporary_snapshot_removed = await access(stateFile).then(() => false, () => true);
const output = process.argv[2] ?? 'run_output/quickstart.json';
await mkdir(dirname(output), { recursive: true });
await writeFile(output, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
