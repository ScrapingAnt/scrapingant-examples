import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { EXTRACTIONS, DIAGNOSTICS } from './cases.mjs';
import { scoreRecords } from './state.mjs';
import { extractionPassed, diagnosticPassed } from './browser_helpers.mjs';

export function summarize(capture) {
  assert.equal(capture.browser, 'chrome', 'Primary packet measures bundled Chrome only');
  assert.equal(capture.rounds, 3, 'Primary comparison requires exactly three rounds');
  assert.deepEqual(capture.runs.map(run => run.round), [1, 2, 3], 'Missing, duplicate or nonconsecutive round');
  const expectedIds = [...Object.keys(EXTRACTIONS), ...DIAGNOSTICS].sort();
  const extractions = [], diagnostics = [];
  for (const run of capture.runs) {
    assert.deepEqual(run.cases.map(item => item.case).sort(), expectedIds, 'Each case must appear exactly once');
    const original = run.cases.find(item => item.case === 'pre_app_seed').page_origin;
    const other = run.cases.find(item => item.case === 'second_origin_guarded').page_origin;
    const originalURL = new URL(original), otherURL = new URL(other);
    assert.equal(originalURL.hostname, '127.0.0.1'); assert.equal(otherURL.hostname, '127.0.0.1');
    assert.equal(originalURL.protocol, 'http:'); assert.equal(otherURL.protocol, 'http:');
    assert.notEqual(originalURL.port, otherURL.port, 'Origin-boundary case must use a different port');
    for (const item of run.cases) {
      assert.equal(typeof item.check_passed, 'boolean');
      if (Object.hasOwn(EXTRACTIONS, item.case)) {
        assert.equal(item.kind, 'extraction');
        const score = scoreRecords(item.records);
        for (const [name, value] of Object.entries(score)) assert.deepEqual(item[name], value, `Stale saved ${name}`);
        assert.equal(item.check_passed, extractionPassed(item.case, item), 'Incorrect extraction check flag');
        const isDirect = item.case.startsWith('direct_');
        assert.equal(item.transport, isDirect ? 'node_http_json' : 'browser_dom', 'Unexpected transport');
        const expectedPath = isDirect ? (item.case === 'direct_query_without_browser' ? '/api/catalog?region=EU' : '/api/catalog')
          : (item.case === 'query_url_without_storage' ? '/catalog?region=EU' : '/catalog');
        assert.equal(item.request_path, expectedPath, 'Unexpected retrieval URL');
        assert.equal(item.page_origin, isDirect ? null : item.case === 'second_origin_guarded' ? other : original);
        extractions.push({ round: run.round, ...item, ...score });
      } else {
        assert.equal(item.kind, 'diagnostic');
        if (item.case === 'storage_event_handshake') {
          assert.ok(Array.isArray(item.writer_probe_events) && Array.isArray(item.other_probe_events));
          assert.equal(item.observation_boundary, 'writer received other-page acknowledgement');
        }
        if (item.case === 'about_blank_storage') assert.equal(item.after_navigation_origin, original);
        assert.equal(item.check_passed, diagnosticPassed(item.case, item), 'Incorrect diagnostic check flag');
        diagnostics.push({ round: run.round, ...item });
      }
    }
  }
  const passed = [...extractions, ...diagnostics].filter(item => item.check_passed).length;
  assert.equal(capture.checks, extractions.length + diagnostics.length, 'Stale headline check total');
  assert.equal(capture.passed_checks, passed, 'Stale headline passed total');
  assert.equal(capture.extraction_observations, extractions.length, 'Stale extraction total');
  assert.equal(capture.diagnostic_observations, diagnostics.length, 'Stale diagnostic total');
  const result = {
    browser: capture.browser, environment: capture.environment, rounds: 3,
    checks: capture.checks, passed_checks: passed,
    extraction_observations: extractions.length, diagnostic_observations: diagnostics.length,
    records_per_extraction: 4, record_opportunities: extractions.length * 4,
    exact_extractions: extractions.filter(item => item.exact_match).length,
    matching_record_observations: extractions.reduce((sum, item) => sum + item.matching_records, 0),
    http_200_extractions: extractions.filter(item => item.target_status === 200).length,
    four_row_extractions: extractions.filter(item => item.row_count === 4).length,
    case_outcomes: {}, diagnostic_outcomes: {},
    limitations: [
      'Self-authored deterministic fixture, not a production reliability or performance estimate.',
      'One bundled Chrome version, three repetitions on one host; Firefox not measured.',
      'The application explicitly maps localStorage.region or a URL query to its catalog request.',
      'Direct URL and JSON retrieval are fixture controls, not an external service test or generic state conversion.',
      'No cookies, login, account state, browser profile persistence, IndexedDB or sessionStorage experiment.',
      'Storage-event writer absence is bounded by receiving the other page acknowledgement.',
      'Quickstart, unit tests and development red tests are excluded from primary observation counts.',
    ],
  };
  for (const id of Object.keys(EXTRACTIONS)) {
    const rows = extractions.filter(item => item.case === id);
    const distinct = key => [...new Set(rows.map(item => item[key]))];
    result.case_outcomes[id] = {
      observations: rows.length, statuses: distinct('target_status'), row_counts: distinct('row_count'),
      matching_record_counts: distinct('matching_records'), storage_regions: distinct('storage_region'),
      startup_regions: distinct('startup_region'), response_regions: distinct('response_region'),
      startup_sources: distinct('startup_source'), operation_request_counts: distinct('catalog_requests_during_operation'),
      all_checks_passed: rows.every(item => item.check_passed),
    };
  }
  for (const id of DIAGNOSTICS) {
    const rows = diagnostics.filter(item => item.case === id);
    result.diagnostic_outcomes[id] = { observations: rows.length, all_checks_passed: rows.every(item => item.check_passed) };
    if (id === 'storage_event_handshake') result.diagnostic_outcomes[id].event_counts = {
      writer_probe_counts: [...new Set(rows.map(item => item.writer_probe_events.length))],
      other_probe_counts: [...new Set(rows.map(item => item.other_probe_events.length))],
    };
  }
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2] ?? 'expected_output/chrome.json';
  const output = process.argv[3] ?? 'run_output/comparison.json';
  const result = summarize(JSON.parse(await readFile(input, 'utf8')));
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ checks: result.checks, exact_extractions: result.exact_extractions,
    extraction_observations: result.extraction_observations, diagnostic_observations: result.diagnostic_observations }));
}
