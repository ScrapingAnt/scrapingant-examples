import test from 'node:test';
import assert from 'node:assert/strict';
import {parseMarker} from './parse-marker.mjs';
const marker = 'sa-extract-' + '1'.repeat(32);
const result = {version: 1, ok: true, data: {text: '</script><!-- &amp; Київ 中文 🕷\n\\"'}};
const html = `<script id="${marker}" type="application/json">${JSON.stringify(result).replace(/</g, '\\u003c')}</script>`;
test('exact protocol preserves special text', () => assert.deepEqual(parseMarker(html, marker), result));
test('missing and duplicate results fail', () => {
  for (const input of ['', html + html]) assert.throws(() => parseMarker(input, marker), /MARKER_COUNT/);
});
test('attribute normalization fails closed', () => assert.throws(() => parseMarker(html.replace(`id="${marker}" type="application/json"`, `type="application/json" id="${marker}"`), marker), /MARKER_FORMAT/));
test('unescaped closing script fails', () => assert.throws(() => parseMarker(html.replaceAll('\\u003c', '<'), marker), /MARKER_FORMAT|JSON_INVALID/));
test('invalid JSON and schema fail', () => {
  assert.throws(() => parseMarker(html.replace('"version":1', '"version":NaN'), marker), /JSON_INVALID/);
  assert.throws(() => parseMarker(html.replace('"version":1', '"version":2'), marker), /SCHEMA_INVALID/);
});
test('application error remains distinct from transport', () => {
  const error = {version: 1, ok: false, error: {code: 'ELEMENT_MISSING'}};
  assert.deepEqual(parseMarker(`<script id="${marker}" type="application/json">${JSON.stringify(error)}</script>`, marker), error);
});
test('array error code is not a string', () => {
  const value = {version: 1, ok: false, error: {code: ['ELEMENT_MISSING']}};
  assert.throws(() => parseMarker(`<script id="${marker}" type="application/json">${JSON.stringify(value)}</script>`, marker), /SCHEMA_INVALID/);
});
test('comment carrier and unquoted duplicate are rejected', () => {
  assert.throws(() => parseMarker(`<!--${html}-->`, marker), /MARKER_COUNT/);
  assert.throws(() => parseMarker(html + `<script id=${marker} type="application/json">{}</script>`, marker), /MARKER_COUNT/);
});
