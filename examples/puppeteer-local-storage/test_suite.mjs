// Capture stable test metadata; keep raw TAP (which can include local paths) in run_output only.
import { readdir, mkdir, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { dirname } from 'node:path';

const files = (await readdir('test')).filter(name => name.endsWith('.test.mjs')).sort().map(name => `test/${name}`);
const result = spawnSync(process.execPath, ['--test', '--test-reporter=tap', ...files], { encoding: 'utf8' });
const count = label => Number(result.stdout.match(new RegExp(`^# ${label} (\\d+)$`, 'm'))?.[1]);
const capture = {
  tested_at: new Date().toISOString(), command: 'node --test test/*.test.mjs',
  node: process.version, tests: count('tests'), passed: count('pass'), failed: count('fail'),
  cancelled: count('cancelled'), skipped: count('skipped'), exit_code: result.status,
  test_names: [...result.stdout.matchAll(/^# Subtest: (.+)$/gm)].map(match => match[1]),
};
const output = process.argv[2] ?? 'run_output/test-results.json';
await mkdir(dirname(output), { recursive: true });
await writeFile(output, JSON.stringify(capture, null, 2) + '\n');
console.log(JSON.stringify(capture, null, 2));
if (result.status !== 0 || !Number.isInteger(capture.tests) || capture.tests !== capture.passed) {
  console.error(result.stdout, result.stderr); process.exitCode = 1;
}
