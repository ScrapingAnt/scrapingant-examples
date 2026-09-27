import test from 'node:test';
import assert from 'node:assert/strict';
import { scoreRecords, validateSnapshot, encodeSnapshot, decodeSnapshot } from '../state.mjs';

const correct = [
  { sku: 'SKU-101', currency: 'EUR', price: '8.10' },
  { sku: 'SKU-202', currency: 'EUR', price: '16.20' },
  { sku: 'SKU-303', currency: 'EUR', price: '24.30' },
  { sku: 'SKU-404', currency: 'EUR', price: '32.40' },
];

test('four literal tuples match in any order', () => {
  assert.deepEqual(scoreRecords([...correct].reverse()), {
    row_count: 4, expected_records: 4, matching_records: 4, exact_match: true,
  });
});
test('four copies of one SKU count as one match', () => {
  const result = scoreRecords(Array(4).fill(correct[0]));
  assert.equal(result.matching_records, 1);
  assert.equal(result.exact_match, false);
});
test('an extra duplicate invalidates an otherwise complete result', () => {
  const result = scoreRecords([...correct, correct[0]]);
  assert.equal(result.matching_records, 4);
  assert.equal(result.exact_match, false);
});
test('a missing SKU and wrong currency do not count as matching records', () => {
  const rows = structuredClone(correct).slice(0, 3);
  rows[0].currency = 'USD';
  delete rows[1].sku;
  assert.equal(scoreRecords(rows).matching_records, 1);
});
test('snapshot JSON round-trips quoted and Unicode string data', () => {
  const state = { origin: 'http://127.0.0.1:8123', entries: [['region', 'EU'], ['text', "quote'\\\n雪</script>"]] };
  assert.deepEqual(decodeSnapshot(encodeSnapshot(state)), state);
});
test('snapshot rejects non-origin URLs and credentials', () => {
  for (const origin of ['http://example.test/path', 'http://u:p@example.test', 'file:///tmp/page', 'null']) {
    assert.throws(() => validateSnapshot({ origin, entries: [] }));
  }
});
test('snapshot rejects duplicate keys before any browser mutation', () => {
  assert.throws(() => validateSnapshot({ origin: 'http://127.0.0.1:8123', entries: [['region', 'EU'], ['region', 'US']] }));
});
test('snapshot rejects nonstring values instead of coercing them', () => {
  assert.throws(() => validateSnapshot({ origin: 'http://127.0.0.1:8123', entries: [['region', { region: 'EU' }]] }));
});
test('snapshot restore rejects a different scheme host or port', () => {
  const state = { origin: 'http://127.0.0.1:8123', entries: [['region', 'EU']] };
  for (const target of ['http://127.0.0.1:8124', 'https://127.0.0.1:8123', 'http://localhost:8123']) {
    assert.throws(() => validateSnapshot(state, target));
  }
});
