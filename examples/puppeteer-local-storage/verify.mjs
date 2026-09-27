// Bind runnable sources and committed captures. No network or browser launch.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir, writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';

async function trackedFiles(directory = '.') {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (['node_modules', '.cache', 'run_output', 'verification.json'].includes(entry.name)) continue;
    const name = directory === '.' ? entry.name : `${directory}/${entry.name}`;
    if (entry.isDirectory()) files.push(...await trackedFiles(name));
    else if (entry.isFile()) files.push(name);
  }
  return files.sort();
}
const mode = process.argv[2] ?? '--check';
if (mode === '--write') {
  const files = {};
  for (const name of await trackedFiles()) files[name] = createHash('sha256').update(await readFile(name)).digest('hex');
  const output = process.argv[3] ?? 'verification.json';
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify({ generated_at: new Date().toISOString(), algorithm: 'sha256',
    scope: 'All packet files except rerun/dependency output and this manifest; commit metadata may require regeneration.', files }, null, 2) + '\n');
  console.log(`Hashed ${Object.keys(files).length} packet files.`);
} else if (mode === '--check') {
  const expected = JSON.parse(await readFile('verification.json', 'utf8'));
  assert.deepEqual(await trackedFiles(), Object.keys(expected.files).sort(), 'Packet file set changed');
  for (const [name, hash] of Object.entries(expected.files)) {
    assert.equal(createHash('sha256').update(await readFile(name)).digest('hex'), hash, `Hash mismatch: ${name}`);
  }
  console.log(`Verified ${Object.keys(expected.files).length} packet file hashes.`);
} else throw new Error('Usage: node verify.mjs [--check|--write [output]]');
