import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {parse} from 'parse5';

export function parseMarker(html, marker) {
  if (!/^sa-extract-[a-f0-9]{32}$/.test(marker)) throw new Error('MARKER_ID');
  const elements = [];
  function visit(node) {
    if (node.attrs?.some(attr => attr.name === 'id' && attr.value === marker)) elements.push(node);
    for (const child of node.childNodes || []) visit(child);
  }
  visit(parse(html));
  if (elements.length !== 1) throw new Error('MARKER_COUNT');
  if (elements[0].tagName !== 'script' || !elements[0].attrs.some(attr => attr.name === 'type' && attr.value === 'application/json')) throw new Error('MARKER_FORMAT');
  const ids = html.match(new RegExp(`\\bid=["']${marker}["']`, 'g')) || [];
  if (ids.length !== 1) throw new Error('MARKER_COUNT');
  const frames = [...html.matchAll(new RegExp(`<script id="${marker}" type="application/json">([^<]*)</script>`, 'g'))];
  if (frames.length !== 1) throw new Error('MARKER_FORMAT');
  let result;
  try { result = JSON.parse(frames[0][1]); } catch { throw new Error('JSON_INVALID'); }
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  if (!object(result) || result.version !== 1 || typeof result.ok !== 'boolean' ||
      (result.ok ? !object(result.data) : !object(result.error) || typeof result.error.code !== 'string' || !/^[A-Z_]{1,64}$/.test(result.error.code))) {
    throw new Error('SCHEMA_INVALID');
  }
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { console.log(JSON.stringify(parseMarker(readFileSync(process.argv[2], 'utf8'), process.argv[3]))); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
