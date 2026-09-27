// Independent literal oracle: never imports the fixture's catalog/pricing code.
const expected = new Map([
  [JSON.stringify(['SKU-101', 'EUR', '8.10']), 1],
  [JSON.stringify(['SKU-202', 'EUR', '16.20']), 1],
  [JSON.stringify(['SKU-303', 'EUR', '24.30']), 1],
  [JSON.stringify(['SKU-404', 'EUR', '32.40']), 1],
]);

export function scoreRecords(rows) {
  if (!Array.isArray(rows)) throw new TypeError('Expected a records array');
  const actual = new Map();
  for (const row of rows) {
    const key = JSON.stringify([row?.sku, row?.currency, row?.price]);
    actual.set(key, (actual.get(key) ?? 0) + 1);
  }
  let matching = 0;
  for (const [key, count] of expected) matching += Math.min(count, actual.get(key) ?? 0);
  return {
    row_count: rows.length, expected_records: 4, matching_records: matching,
    exact_match: matching === 4 && rows.length === 4,
  };
}

// A separate literal control oracle prevents arbitrary non-EUR garbage from passing.
const expectedUSD = new Map([
  [JSON.stringify(['SKU-101', 'USD', '9.00']), 1],
  [JSON.stringify(['SKU-202', 'USD', '18.00']), 1],
  [JSON.stringify(['SKU-303', 'USD', '27.00']), 1],
  [JSON.stringify(['SKU-404', 'USD', '36.00']), 1],
]);
export function matchesRegionDataset(rows, region) {
  if (region === 'EU') return scoreRecords(rows).exact_match;
  if (region !== 'US') throw new Error('Unknown fixture region');
  const actual = new Map();
  for (const row of rows) {
    const key = JSON.stringify([row?.sku, row?.currency, row?.price]);
    actual.set(key, (actual.get(key) ?? 0) + 1);
  }
  return actual.size === expectedUSD.size
    && [...expectedUSD].every(([key, count]) => actual.get(key) === count);
}

export function validateSnapshot(snapshot, intendedOrigin) {
  if (!snapshot || typeof snapshot.origin !== 'string' || !Array.isArray(snapshot.entries)) {
    throw new TypeError('Expected an origin and entries array');
  }
  const origin = new URL(snapshot.origin);
  if (!['http:', 'https:'].includes(origin.protocol) || origin.origin !== snapshot.origin) {
    throw new TypeError('Expected a canonical HTTP(S) origin without credentials or path');
  }
  if (intendedOrigin !== undefined && snapshot.origin !== intendedOrigin) {
    throw new Error('Snapshot origin does not match the intended origin');
  }
  const names = new Set();
  for (const entry of snapshot.entries) {
    if (!Array.isArray(entry) || entry.length !== 2 || entry.some(value => typeof value !== 'string')) {
      throw new TypeError('Every storage entry must be a pair of strings');
    }
    if (names.has(entry[0])) throw new TypeError('Duplicate storage key');
    names.add(entry[0]);
  }
  return snapshot;
}

export function encodeSnapshot(snapshot) { return JSON.stringify(validateSnapshot(snapshot)); }
export function decodeSnapshot(text, intendedOrigin) { return validateSnapshot(JSON.parse(text), intendedOrigin); }

export async function installSnapshot(page, snapshot, intendedOrigin) {
  validateSnapshot(snapshot, intendedOrigin);
  return page.evaluateOnNewDocument(data => {
    if (location.origin !== data.origin) return;
    for (const [key, value] of data.entries) localStorage.setItem(key, value);
  }, snapshot);
}

export async function captureSnapshot(page) {
  const snapshot = await page.evaluate(() => ({
    origin: location.origin,
    entries: Array.from({ length: localStorage.length }, (_, index) => {
      const key = localStorage.key(index);
      return [key, localStorage.getItem(key)];
    }).sort(([a], [b]) => a.localeCompare(b)),
  }));
  return validateSnapshot(snapshot);
}
