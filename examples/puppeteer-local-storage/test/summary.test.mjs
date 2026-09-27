import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { summarize } from '../summarize.mjs';

function capture() {
  return JSON.parse(readFileSync(new URL('../expected_output/chrome.json', import.meta.url), 'utf8'));
}
test('separate record and diagnostic denominators reflect the complete capture', () => {
  const result = summarize(capture());
  assert.equal(result.extraction_observations, 36);
  assert.equal(result.diagnostic_observations, 12);
  assert.equal(result.record_opportunities, 144);
  assert.equal(result.exact_extractions, 21);
  assert.equal(result.matching_record_observations, 84);
});
test('duplicate records with stale saved scores are rejected', () => {
  const data = capture(); const item = data.runs[0].cases.find(item => item.exact_match);
  item.records = Array(4).fill(item.records[0]);
  assert.throws(() => summarize(data));
});
test('changed record price with stale saved scores is rejected', () => {
  const data = capture(); const item = data.runs[0].cases.find(item => item.exact_match);
  item.records[0].price = '0.00'; assert.throws(() => summarize(data));
});
test('duplicate case cannot replace a missing case', () => {
  const data = capture(); data.runs[0].cases[1] = structuredClone(data.runs[0].cases[0]);
  assert.throws(() => summarize(data));
});
test('missing case is rejected', () => {
  const data = capture(); data.runs[0].cases.pop(); assert.throws(() => summarize(data));
});
test('duplicate or nonconsecutive rounds are rejected', () => {
  const data = capture(); data.runs[1].round = 1; assert.throws(() => summarize(data));
});
test('missing whole round is rejected despite internally consistent records', () => {
  const data = capture(); data.runs.pop(); assert.throws(() => summarize(data));
});
test('wrong case kind cannot change the denominator', () => {
  const data = capture(); data.runs[0].cases.find(item => item.kind === 'extraction').kind = 'diagnostic';
  assert.throws(() => summarize(data));
});
test('a stale DOM observation cannot masquerade as a reload', () => {
  const data = capture(); data.runs[0].cases.find(item => item.case === 'late_write_stale_dom').catalog_requests_during_operation = 1;
  assert.throws(() => summarize(data));
});
test('contradictory diagnostic check flag is rejected', () => {
  const data = capture(); data.runs[0].cases.find(item => item.case === 'storage_event_handshake').writer_probe_events.push({ key: 'probe' });
  assert.throws(() => summarize(data));
});
test('serialized headline totals must agree with recomputed totals', () => {
  const data = capture(); data.extraction_observations = 999; assert.throws(() => summarize(data));
});
test('zero desired matches cannot conceal a corrupted USD control record', () => {
  const data = capture(); const item = data.runs[0].cases.find(item => item.case === 'fresh_page');
  item.records[0].price = '0.00'; assert.throws(() => summarize(data));
});
test('second-origin control cannot be relabeled as the primary origin', () => {
  const data = capture();
  data.runs[0].cases.find(item => item.case === 'second_origin_guarded').page_origin =
    data.runs[0].cases.find(item => item.case === 'pre_app_seed').page_origin;
  assert.throws(() => summarize(data));
});
