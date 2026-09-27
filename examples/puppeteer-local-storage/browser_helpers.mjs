import os from 'node:os';
import { createRequire } from 'node:module';
import puppeteer from 'puppeteer';
import { requestJSON } from './fixture.mjs';
import { scoreRecords, matchesRegionDataset } from './state.mjs';
import { EXTRACTIONS, TRANSPORT_PROBE } from './cases.mjs';

const require = createRequire(import.meta.url);
export async function launchBrowser() {
  const noSandbox = process.env.PUPPETEER_NO_SANDBOX === '1';
  if (noSandbox && process.env.CI !== 'true') throw new Error('Sandbox opt-out is restricted to an explicit CI=true run');
  return puppeteer.launch({ headless: true, args: noSandbox ? ['--no-sandbox'] : [] });
}
export async function environment(browser) {
  return {
    node: process.version, puppeteer: require('puppeteer/package.json').version,
    browser: await browser.version(), os: os.type(), os_release: os.release(), architecture: os.arch(),
    sandbox_disabled: process.env.PUPPETEER_NO_SANDBOX === '1',
  };
}
export async function readPage(page, navigationStatus, requestDelta) {
  return page.evaluate(({ navigationStatus, requestDelta }) => ({
    transport: 'browser_dom', navigation_status: navigationStatus,
    page_origin: location.origin, request_path: location.pathname + location.search,
    ...window.catalogObservation, storage_region: localStorage.getItem('region'),
    storage_length: localStorage.length, catalog_requests_during_operation: requestDelta,
    records: [...document.querySelectorAll('tbody tr')].map(row => {
      const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent);
      return { sku: cells[0], currency: cells[1], price: cells[2] };
    }),
  }), { navigationStatus, requestDelta });
}
export async function navigateCatalog(page, fixture, suffix = '/catalog', reload = false) {
  const before = fixture.catalogRequests;
  const response = reload ? await page.reload({ waitUntil: 'load' }) : await page.goto(fixture.origin + suffix, { waitUntil: 'load' });
  await page.waitForSelector('body[data-ready="yes"]', { timeout: 10000 });
  return readPage(page, response.status(), fixture.catalogRequests - before);
}
export async function directCatalog(fixture, query = '') {
  const before = fixture.catalogRequests;
  const response = await requestJSON(`${fixture.origin}/api/catalog${query}`);
  return {
    transport: 'node_http_json', navigation_status: null, target_status: response.status,
    page_origin: null, request_path: `/api/catalog${query}`,
    startup_region: null, startup_source: 'no_browser', storage_region: null, storage_length: null,
    response_region: response.body.region, catalog_requests_during_operation: fixture.catalogRequests - before,
    records: response.body.records,
  };
}
export function extractionPassed(caseId, observation) {
  const expected = EXTRACTIONS[caseId];
  const score = scoreRecords(observation.records);
  const browser = observation.transport === 'browser_dom';
  return observation.target_status === 200 && score.row_count === 4
    && matchesRegionDataset(observation.records, expected.region)
    && score.matching_records === expected.matches && score.exact_match === (expected.matches === 4)
    && observation.storage_region === expected.storage && observation.response_region === expected.region
    && observation.startup_source === expected.source
    && observation.catalog_requests_during_operation === expected.requests
    && (browser ? observation.navigation_status === 200 && observation.startup_region === expected.region
      : observation.transport === 'node_http_json' && observation.navigation_status === null && observation.startup_region === null)
    && (expected.storage === null && browser ? observation.storage_length === 0 : true);
}
export function extraction(caseId, observation) {
  return { case: caseId, kind: 'extraction', ...observation, ...scoreRecords(observation.records),
    check_passed: extractionPassed(caseId, observation) };
}
export function diagnosticPassed(caseId, observed) {
  switch (caseId) {
    case 'about_blank_storage': return observed.page_url === 'about:blank' && observed.error_name === 'SecurityError'
      && observed.after_navigation_value === 'EU' && new URL(observed.after_navigation_origin).protocol === 'http:';
    case 'storage_event_handshake': return observed.writer_probe_events.length === 0
      && observed.other_probe_events.length === 1 && observed.ack_received === true
      && observed.other_probe_events[0].oldValue === null && observed.other_probe_events[0].newValue === 'synthetic-event-value'
      && observed.other_probe_events[0].key === 'probe' && observed.other_probe_events[0].local_storage === true;
    case 'node_browser_boundary': return observed.error_name === 'ReferenceError'
      && observed.node_value === 'node-computed:synthetic' && observed.stored_argument === observed.node_value;
    case 'json_argument_transport': return JSON.stringify(observed.returned) === JSON.stringify(TRANSPORT_PROBE)
      && typeof observed.raw_storage === 'string' && JSON.stringify(JSON.parse(observed.raw_storage)) === JSON.stringify(TRANSPORT_PROBE)
      && observed.injected === false;
    default: throw new Error('Unknown diagnostic');
  }
}
export function diagnostic(caseId, observed) {
  return { case: caseId, kind: 'diagnostic', ...observed, check_passed: diagnosticPassed(caseId, observed) };
}
