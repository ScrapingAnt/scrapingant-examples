import { mkdir, readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { startFixture } from './fixture.mjs';
import { captureSnapshot, encodeSnapshot, decodeSnapshot, installSnapshot } from './state.mjs';
import { TRANSPORT_PROBE } from './cases.mjs';
import { launchBrowser, environment, readPage, navigateCatalog, directCatalog, extraction, diagnostic } from './browser_helpers.mjs';

async function oneRound(browser, primary, secondary, round) {
  const contexts = [];
  const temporary = await mkdtemp(join(tmpdir(), 'synthetic-puppeteer-storage-'));
  async function newContext() {
    const context = await browser.createBrowserContext(); contexts.push(context); return context;
  }
  const cases = [];
  try {
    const freshContext = await newContext();
    const fresh = await freshContext.newPage();
    const blankResult = await fresh.evaluate(() => {
      try { localStorage.setItem('region', 'EU'); return { error_name: null }; }
      catch (error) { return { error_name: error.name }; }
    });
    const blankPageUrl = fresh.url();
    cases.push(extraction('fresh_page', await navigateCatalog(fresh, primary)));
    const beforeWrite = primary.catalogRequests;
    const afterNavigationValue = await fresh.evaluate(value => {
      localStorage.setItem('region', value); return localStorage.getItem('region');
    }, 'EU');
    cases.push(diagnostic('about_blank_storage', { page_url: blankPageUrl, ...blankResult,
      after_navigation_value: afterNavigationValue, after_navigation_origin: primary.origin }));
    cases.push(extraction('late_write_stale_dom', await readPage(fresh, 200, primary.catalogRequests - beforeWrite)));
    cases.push(extraction('late_write_then_reload', await navigateCatalog(fresh, primary, '/catalog', true)));

    const seededContext = await newContext();
    const seeded = await seededContext.newPage();
    await installSnapshot(seeded, { origin: primary.origin, entries: [['region', 'EU']] }, primary.origin);
    cases.push(extraction('pre_app_seed', await navigateCatalog(seeded, primary)));
    const snapshot = await captureSnapshot(seeded);
    const stateFile = join(temporary, 'storage.json');
    await writeFile(stateFile, encodeSnapshot(snapshot), { mode: 0o600 });
    const restoredContext = await newContext();
    const restored = await restoredContext.newPage();
    await installSnapshot(restored, decodeSnapshot(await readFile(stateFile, 'utf8'), primary.origin), primary.origin);
    cases.push(extraction('snapshot_fresh_context', await navigateCatalog(restored, primary)));
    const shared = await seededContext.newPage();
    cases.push(extraction('same_context_new_page', await navigateCatalog(shared, primary)));
    const isolated = await (await newContext()).newPage();
    cases.push(extraction('isolated_context', await navigateCatalog(isolated, primary)));
    cases.push(extraction('second_origin_guarded', await navigateCatalog(seeded, secondary)));
    cases.push(extraction('return_to_original_origin', await navigateCatalog(seeded, primary)));
    const queryPage = await (await newContext()).newPage();
    cases.push(extraction('query_url_without_storage', await navigateCatalog(queryPage, primary, '/catalog?region=EU')));
    cases.push(extraction('direct_query_without_browser', await directCatalog(primary, '?region=EU')));
    cases.push(extraction('direct_missing_query', await directCatalog(primary)));

    // Deterministic event boundary: other page receives probe, writes ack, writer receives ack.
    // The timer is a failure deadline, never an arbitrary delay before reading counts.
    const eventsContext = await newContext();
    const writer = await eventsContext.newPage();
    const reader = await eventsContext.newPage();
    await writer.goto(primary.origin + '/blank'); await reader.goto(primary.origin + '/blank');
    await reader.evaluate(() => {
      window.probeEvents = [];
      addEventListener('storage', event => {
        if (event.key !== 'probe') return;
        window.probeEvents.push({ key: event.key, oldValue: event.oldValue, newValue: event.newValue,
          local_storage: event.storageArea === localStorage });
        localStorage.setItem('ack', event.newValue);
      });
    });
    const eventResult = await writer.evaluate(() => new Promise((resolve, reject) => {
      const events = [];
      const timer = setTimeout(() => { removeEventListener('storage', listener); reject(new Error('Storage-event acknowledgement timed out')); }, 5000);
      function listener(event) {
        if (event.key === 'probe') events.push({ key: event.key, newValue: event.newValue });
        if (event.key === 'ack' && event.newValue === 'synthetic-event-value') {
          clearTimeout(timer); removeEventListener('storage', listener);
          resolve({ writer_probe_events: events, ack_received: true });
        }
      }
      addEventListener('storage', listener);
      localStorage.setItem('probe', 'synthetic-event-value');
    }));
    cases.push(diagnostic('storage_event_handshake', { ...eventResult,
      other_probe_events: await reader.evaluate(() => window.probeEvents), observation_boundary: 'writer received other-page acknowledgement' }));

    const nodeOnlyHelper = value => `node-computed:${value}`;
    const boundaryResult = await writer.evaluate(() => {
      try { return { returned: nodeOnlyHelper('synthetic'), error_name: null }; }
      catch (error) { return { error_name: error.name }; }
    });
    const nodeValue = nodeOnlyHelper('synthetic');
    const storedArgument = await writer.evaluate(value => {
      localStorage.setItem('node-result', value); return localStorage.getItem('node-result');
    }, nodeValue);
    cases.push(diagnostic('node_browser_boundary', { ...boundaryResult, node_value: nodeValue, stored_argument: storedArgument }));
    const transported = await writer.evaluate(value => {
      window.injected = false;
      localStorage.setItem('json-probe', JSON.stringify(value));
      const raw = localStorage.getItem('json-probe');
      return { returned: JSON.parse(raw), raw_storage: raw, injected: window.injected };
    }, TRANSPORT_PROBE);
    cases.push(diagnostic('json_argument_transport', transported));
    return { round, cases };
  } finally {
    await Promise.all(contexts.map(context => context.close()));
    await rm(temporary, { recursive: true, force: true });
  }
}

export async function runMatrix(rounds = 3) {
  const primary = await startFixture();
  let secondary, browser;
  try {
    secondary = await startFixture(); browser = await launchBrowser();
    const result = { tested_at: new Date().toISOString(), browser: 'chrome', environment: await environment(browser),
      fixture: 'self-authored loopback catalog; two distinct HTTP ports; synthetic localStorage only',
      rounds, runs: [] };
    for (let round = 1; round <= rounds; round += 1) result.runs.push(await oneRound(browser, primary, secondary, round));
    const cases = result.runs.flatMap(run => run.cases);
    result.checks = cases.length;
    result.passed_checks = cases.filter(item => item.check_passed).length;
    result.extraction_observations = cases.filter(item => item.kind === 'extraction').length;
    result.diagnostic_observations = cases.filter(item => item.kind === 'diagnostic').length;
    return result;
  } finally {
    if (browser) await browser.close();
    if (secondary) await secondary.close();
    await primary.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const output = process.argv[2] ?? 'run_output/chrome.json';
  const result = await runMatrix(3);
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ checks: result.checks, passed_checks: result.passed_checks,
    extraction_observations: result.extraction_observations, diagnostic_observations: result.diagnostic_observations }));
  if (result.checks !== result.passed_checks) process.exitCode = 1;
}
