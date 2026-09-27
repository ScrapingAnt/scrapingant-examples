import test from 'node:test';
import assert from 'node:assert/strict';
import { startFixture, requestJSON } from '../fixture.mjs';

test('explicit region query chooses records independently of browser storage', async () => {
  const fixture = await startFixture();
  try {
    const eu = await requestJSON(`${fixture.origin}/api/catalog?region=EU`);
    assert.equal(eu.status, 200);
    assert.deepEqual(eu.body.records[0], { sku: 'SKU-101', currency: 'EUR', price: '8.10' });
    const us = await requestJSON(`${fixture.origin}/api/catalog`);
    assert.deepEqual(us.body.records[3], { sku: 'SKU-404', currency: 'USD', price: '36.00' });
    assert.equal(fixture.catalogRequests, 2);
  } finally { await fixture.close(); }
});
test('direct request helper rejects non-loopback targets', async () => {
  await assert.rejects(() => requestJSON('http://example.test/api/catalog'));
});
