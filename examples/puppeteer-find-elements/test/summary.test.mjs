import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {summarize} from '../summarize.mjs';
const baseline=JSON.parse(readFileSync(new URL('../expected_output/chrome.json',import.meta.url),'utf8'));
test('strict summary recomputes the captured matrix',()=>assert.equal(summarize(baseline).passed_checks,63));
const mutations=[
 ['absent round',x=>x.runs.pop()],
 ['duplicate round',x=>{x.runs[1].round=1;}],
 ['missing case',x=>x.runs[0].cases.pop()],
 ['duplicate case',x=>{x.runs[0].cases[1]=x.runs[0].cases[0];}],
 ['stale headline count',x=>{x.checks=99;}],
 ['forged success flag',x=>{x.runs[0].cases[0].check_passed=false;}],
 ['changed records despite saved pass',x=>{x.runs[0].cases.find(c=>c.case==='scoped_css').records[0].price='999.00';}],
 ['changed text despite saved sentinel flags',x=>{x.runs[0].cases.find(c=>c.case==='body_inner_text').text+=' HIDDEN_SENTINEL';}],
 ['forged sentinel flags',x=>{x.runs[0].cases.find(c=>c.case==='body_text_content').sentinels.hidden=false;}],
 ['detached-handle claim without boundary',x=>{x.runs[0].cases.find(c=>c.case==='replaced_old_handle').connected=true;}],
 ['missing selector no-error result',x=>{x.runs[0].cases.find(c=>c.case==='missing_apis').eval_error=null;}],
 ['cross-boundary selector leakage',x=>{x.runs[0].cases.find(c=>c.case==='boundary_queries').main_frame=1;}],
 ['wrong HTTP status',x=>{x.runs[0].navigation_status=404;}],
 ['unknown top-level metadata',x=>{x.unverified='x';}],
 ['unexpected per-case metadata',x=>{x.runs[0].cases[0].extra='x';}],
];
for(const [name,mutate] of mutations)test(`summary rejects ${name}`,()=>{
 const value=structuredClone(baseline);mutate(value);assert.throws(()=>summarize(value));
});
