import assert from 'node:assert/strict';
// Deliberately literal and independent of fixture data/construction code.
export const EXPECTED = Object.freeze([
 Object.freeze({sku:'A101',title:'Ant Field Kit',currency:'USD',price:'19.95',href:'/p/a101'}),
 Object.freeze({sku:'B202',title:'Sugar & Water Feeder',currency:'USD',price:'7.50',href:'/p/b202'}),
 Object.freeze({sku:'C303',title:'Tunnel Kit — Mini',currency:'USD',price:'12.00',href:'/p/c303'}),
]);
export const DECOY = Object.freeze({sku:'DECOY',title:'Promotional decoy',currency:'USD',price:'0.01',href:'/promotion'});
export const SHADOW = Object.freeze({sku:'SHADOW',title:'Shadow product',currency:'USD',price:'4.00',href:'/p/shadow'});
export const FRAME = Object.freeze({sku:'FRAME',title:'Frame product',currency:'USD',price:'6.00',href:'/p/frame'});
export const REVISED = Object.freeze({sku:'A101',title:'Ant Field Kit — revised',currency:'USD',price:'19.95',href:'/p/a101'});
export const UNPOPULATED = Object.freeze([
 {sku:'A101',title:'',currency:'USD',price:'',href:'/p/a101'},
 {sku:'B202',title:'',currency:'USD',price:'',href:'/p/b202'},
 {sku:'C303',title:'',currency:'USD',price:'',href:'/p/c303'},
]);
export function validateRecords(records, expected=EXPECTED) {
 assert.ok(Array.isArray(records),'records must be an array');
 assert.equal(new Set(records.map(row=>row?.sku)).size, records.length,'duplicate SKU');
 for(const row of records){
  assert.deepEqual(Object.keys(row).sort(),['currency','href','price','sku','title']);
  for(const value of Object.values(row)) assert.equal(typeof value,'string');
 }
 assert.deepEqual(records,expected,'records must match independent literal tuples'); return true;
}
export const EXTRACTIONS = Object.freeze({
 global_first:[DECOY],global_all:[DECOY,...EXPECTED],scoped_css:EXPECTED,scoped_handles:EXPECTED,
 xpath_all:EXPECTED,text_selector:[EXPECTED[1]],eval_first:[EXPECTED[0]],presence_only:UNPOPULATED,
 populated_wait:EXPECTED,replaced_old_handle:[EXPECTED[0]],replaced_fresh:[REVISED,...EXPECTED.slice(1)],
 open_shadow:[SHADOW],iframe:[FRAME],
});
export const TEXT_EXPECTED = Object.freeze({
 body_inner_text:{visible:true,hidden:false,script:false,style:false,catalog:true},
 body_text_content:{visible:true,hidden:true,script:true,style:true,catalog:true},
 body_selection:{visible:true,hidden:false,script:false,style:false,catalog:true},
 raw_html_to_text:{visible:true,hidden:true,script:false,style:false,catalog:false},
 rendered_html_to_text:{visible:true,hidden:true,script:false,style:false,catalog:true},
});
export const DIAGNOSTICS=['missing_apis','attributes_properties','boundary_queries'];
export function sentinels(text){
 assert.equal(typeof text,'string'); return {visible:text.includes('VISIBLE_SENTINEL'),hidden:text.includes('HIDDEN_SENTINEL'),script:text.includes('SCRIPT_SENTINEL'),style:text.includes('STYLE_SENTINEL'),catalog:text.includes('Sugar & Water Feeder')};
}
