import assert from 'node:assert/strict';
import {readdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {summarize} from './summarize.mjs';
const root=new URL('./',import.meta.url);
const sourceNames=(await readdir(root)).filter(name=>/\.(mjs|sh)$/.test(name)||['package.json','package-lock.json','.gitignore'].includes(name));
for(const folder of ['fixtures','test']) for(const name of await readdir(new URL(folder+'/',root)))sourceNames.push(folder+'/'+name);
const artifactNames=(await readdir(new URL('expected_output/',root))).map(name=>'expected_output/'+name).concat('comparison.json');
async function hashes(names){const result={};for(const name of names.sort())result[name]=createHash('sha256').update(await readFile(new URL(name,root))).digest('hex');return result;}
const sourceHashes=await hashes(sourceNames),artifactHashes=await hashes(artifactNames);
const capture=JSON.parse(await readFile(new URL('expected_output/chrome.json',root),'utf8'));
const computed=summarize(capture),saved=JSON.parse(await readFile(new URL('comparison.json',root),'utf8'));
assert.deepEqual(saved,computed,'saved comparison must recompute from raw capture');
const tests=JSON.parse(await readFile(new URL('expected_output/test-results.json',root),'utf8'));
assert.equal(tests.tests,tests.passed);assert.equal(tests.failed,0);assert.equal(tests.exit_code,0);assert.equal(tests.tests,31);
const manifest={schema_version:1,source_hashes:sourceHashes,artifact_hashes:artifactHashes,raw_capture_recomputed:true,boundary_tests:tests.tests,checks:computed.checks,source_commit:'ec6d98bbbcee501ebf4d1d137d572e36060dfc2c',linux_ci:'https://github.com/ScrapingAnt/scrapingant-examples/actions/runs/36403589363'};
if(process.argv[2]==='--record')await writeFile(new URL('verification.json',root),JSON.stringify(manifest,null,2)+'\n');
else assert.deepEqual(JSON.parse(await readFile(new URL('verification.json',root),'utf8')),manifest,'frozen source/artifact hashes changed');
console.log(JSON.stringify({source_files:Object.keys(sourceHashes).length,artifacts:Object.keys(artifactHashes).length,checks:computed.checks,boundary_tests:tests.tests,hashes_match:true}));
