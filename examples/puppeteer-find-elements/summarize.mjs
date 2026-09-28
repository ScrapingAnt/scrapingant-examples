import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {EXTRACTIONS,TEXT_EXPECTED,DIAGNOSTICS,EXPECTED,validateRecords,sentinels} from './oracle.mjs';
const keys=(value,expected)=>assert.deepEqual(Object.keys(value).sort(),expected.sort(),'unexpected/missing object fields');
export function summarize(capture){
 keys(capture,['schema_version','browser','tested_at','rounds','environment','runs','extraction_observations','diagnostic_observations','text_diagnostic_observations','checks','passed_checks']);
 assert.equal(capture.schema_version,1);assert.equal(capture.browser,'chrome');assert.equal(capture.rounds,3);
 assert.ok(!Number.isNaN(Date.parse(capture.tested_at)),'capture timestamp');
 keys(capture.environment,['node','puppeteer','html_to_text','browser','os','os_release','architecture','sandbox_disabled']);
 assert.equal(typeof capture.environment.sandbox_disabled,'boolean');
 assert.match(capture.environment.node,/^v22\./);assert.equal(capture.environment.puppeteer,'25.12.0');assert.equal(capture.environment.html_to_text,'9.0.5');assert.match(capture.environment.browser,/Chrome\//);
 assert.deepEqual(capture.runs.map(run=>run.round),[1,2,3]);
 const ids=[...Object.keys(EXTRACTIONS),...DIAGNOSTICS,...Object.keys(TEXT_EXPECTED)].sort();
 let extraction=0,diagnostic=0,texts=0,exactCatalog=0;
 for(const run of capture.runs){
  keys(run,['round','navigation_status','raw_html_http_status','cases']);assert.equal(run.navigation_status,200);assert.equal(run.raw_html_http_status,200);
  assert.deepEqual(run.cases.map(item=>item.case).sort(),ids,'case coverage');
  for(const item of run.cases){
   assert.equal(item.check_passed,true,'saved result flag');
   if(Object.hasOwn(EXTRACTIONS,item.case)){
    const extra=item.case==='replaced_old_handle'?['connected']:['presence_only','populated_wait'].includes(item.case)?['boundary']:[];
    keys(item,['case','kind','records','check_passed',...extra]);
    assert.equal(item.kind,'extraction');validateRecords(item.records,EXTRACTIONS[item.case]);extraction++;
    if(JSON.stringify(item.records)===JSON.stringify(EXPECTED))exactCatalog++;
    if(item.case==='replaced_old_handle')assert.equal(item.connected,false,'old handle must be detached');
    if(item.case==='presence_only')assert.equal(item.boundary,'card exists; application population gate still closed');
    if(item.case==='populated_wait')assert.equal(item.boundary,'explicit release acknowledged; every title and decimal price populated');
   }else if(Object.hasOwn(TEXT_EXPECTED,item.case)){
    keys(item,['case','kind','text','sentinels','check_passed']);
    assert.equal(item.kind,'text_diagnostic');assert.deepEqual(sentinels(item.text),TEXT_EXPECTED[item.case]);assert.deepEqual(item.sentinels,sentinels(item.text));texts++;
   }else{
    assert.equal(item.kind,'diagnostic');diagnostic++;
    if(item.case==='missing_apis'){
     keys(item,['case','kind','single','all','eval_error','multi_eval','check_passed']);keys(item.eval_error,['name','message']);
     assert.equal(item.single,null);assert.deepEqual(item.all,[]);assert.deepEqual(item.multi_eval,[]);
     assert.equal(item.eval_error?.name,'Error');assert.match(item.eval_error.message,/#missing/);
    }else if(item.case==='attributes_properties'){
     keys(item,['case','kind','missing_attribute','raw_href','resolved_href_path','resolved_href_is_absolute','text','check_passed']);
     assert.equal(item.missing_attribute,null);assert.equal(item.raw_href,'/p/b202');assert.equal(item.resolved_href_path,'/p/b202');assert.equal(item.resolved_href_is_absolute,true);assert.equal(item.text,'Sugar & Water Feeder');
    }else if(item.case==='boundary_queries'){
     keys(item,['case','kind','main_shadow','main_frame','shadow_open','check_passed']);
     assert.equal(item.main_shadow,0);assert.equal(item.main_frame,0);assert.equal(item.shadow_open,'open');
    }else assert.fail('unknown diagnostic');
   }
  }
 }
 assert.equal(extraction,39);assert.equal(diagnostic,9);assert.equal(texts,15);
 assert.equal(capture.extraction_observations,extraction);assert.equal(capture.diagnostic_observations,diagnostic);assert.equal(capture.text_diagnostic_observations,texts);
 assert.equal(capture.checks,extraction+diagnostic+texts);assert.equal(capture.passed_checks,capture.checks);
 return {schema_version:1,browser:capture.browser,environment:capture.environment,rounds:3,checks:capture.checks,passed_checks:capture.checks,extraction_observations:extraction,diagnostic_observations:diagnostic,text_diagnostic_observations:texts,exact_three_record_catalogue_observations:exactCatalog,
  extraction_cases:Object.fromEntries(Object.entries(EXTRACTIONS).map(([id,rows])=>[id,{observations:3,expected_rows:rows.length,expected_skus:rows.map(row=>row.sku),all_passed:true}])),
  text_cases:Object.fromEntries(Object.entries(TEXT_EXPECTED).map(([id,markers])=>[id,{observations:3,expected_sentinels:markers,all_passed:true}])),
  limitations:['Synthetic loopback fixture; no production performance or reliability inference.','One bundled Chrome version and host, three repetitions; Firefox not measured.','Application population is released by an explicit test handshake; no arbitrary delay.','Raw HTML conversion does not execute the page script or apply browser CSS.','A detached handle can still read its old node in this same-document replacement case; this does not promise survival across navigation.','Text diagnostics assert declared sentinels; they do not claim identical whitespace across engines or platforms.','No Bing or display-optimization recovery claim; no clipboard or keyboard action.','Quickstarts and boundary tests are outside primary matrix denominators.','ScrapingAnt evidence belongs to the shared javascript-dom-extraction packet.']};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const input=process.argv[2]??'expected_output/chrome.json',output=process.argv[3]??'run_output/comparison.json';
 const result=summarize(JSON.parse(await readFile(input,'utf8')));await mkdir(dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({checks:result.checks,passed:result.passed_checks}));
}
