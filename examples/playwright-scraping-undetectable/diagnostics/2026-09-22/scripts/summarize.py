"""Summarize named UI observations; unknown or incomplete results never count as passes."""
import argparse,json
from urllib.parse import urlsplit
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
labels={'Webdriver','User-Agent','CDP','Navigator'}
parser=argparse.ArgumentParser()
parser.add_argument('--require-complete',action='store_true',help='Require all28 valid runs, including28 BrowserScan and14 Sannysoft captures')
args=parser.parse_args()
# Dated schema observed on September22; changes require inspection, never an implicit pass.
expected_sannysoft={
 'User Agent (Old)','WebDriver (New)','WebDriver Advanced','Chrome (New)',
 'Permissions (New)','Plugins Length (Old)','Plugins is of type PluginArray',
 'Languages (Old)','WebGL Vendor','WebGL Renderer','Broken Image Dimensions',
 'PHANTOM_UA','PHANTOM_PROPERTIES','PHANTOM_ETSL','PHANTOM_LANGUAGE',
 'PHANTOM_WEBSOCKET','MQ_SCREEN','PHANTOM_OVERFLOW','PHANTOM_WINDOW_HEIGHT',
 'HEADCHR_UA','HEADCHR_CHROME_OBJ','HEADCHR_PERMISSIONS','HEADCHR_PLUGINS',
 'HEADCHR_IFRAME','CHR_DEBUG_TOOLS','SELENIUM_DRIVER','CHR_BATTERY',
 'CHR_MEMORY','TRANSPARENT_PIXEL','SEQUENTUM','VIDEO_CODECS'
}
expected_keys={f'{a}-{m}-{r}' for a in ['chrome-control','patchright','python-stealth','extra-stealth','rebrowser','firefox-control','camoufox'] for m in ['headless','headed'] for r in [1,2]}
expected_urls={'browserscan':('www.browserscan.net','/bot-detection'),'sannysoft':('bot.sannysoft.com','/')}

rows=[]
for p in sorted((ROOT/'results').glob('*.json')):
 d=json.loads(p.read_text());row={k:d[k] for k in ['key','approach','mode','repetition']};row['browser_version']=d.get('browser_version');row['launch_error']=d.get('launch_error')
 for item in d['pages']:
  if item['site']=='local':row['local_properties']=item.get('properties');continue
  name=item['site'];out={'http_status':item.get('http_status'),'error':item.get('error'),'screenshot':item.get('screenshot')}
  if not item.get('error'):
   snap=item.get('snapshot_10s');old=item.get('snapshot_6s')
   assert snap is not None and old is not None,(p,name,'missing snapshot')
   assert item.get('http_status')==200,(p,name,'unexpected HTTP status')
   for snapshot in [old,snap]:
    url=urlsplit(snapshot['url'])
    assert (url.hostname,url.path)==expected_urls[name],(p,name,'unexpected final URL')
   if name=='browserscan':
    for snapshot in [old,snap]:
     assert len(snapshot['summary'])==4 and {x['label'] for x in snapshot['summary']}==labels,(p,'summary labels changed')
     assert all(x['color'] in ['rgb(251, 81, 56)','rgb(255, 255, 255)'] for x in snapshot['summary']),(p,'unrecognized UI colors')
     assert snapshot['verdict'].split(':',1)[-1].strip() in ['Robot','Normal'],(p,'unknown verdict')
    out['verdict']=snap['verdict'].split(':',1)[-1].strip()
    assert out['verdict'] in ['Robot','Normal'],(p,'unknown BrowserScan verdict')
    out['flagged']=[x['label'] for x in snap['summary'] if x['color']=='rgb(251, 81, 56)']
    out['stable_6_to_10s']=old['verdict']==snap['verdict'] and old['summary']==snap['summary']
   else:
    def states(s):
     return [(r['cells'][0]['text'],r['cells'][1]['class']) for r in s['rows'] if len(r['cells'])>=2 and any(t in r['cells'][1]['class'].split() for t in ['passed','failed','warn'])]
    observed=states(snap);out['classified_rows']=len(observed)
    for snapshot in [old,snap]:
     checks=states(snapshot)
     assert all(len(set(c.split()) & {'passed','failed','warn'})==1 for n,c in checks),(p,'ambiguous Sannysoft state')
     assert len(checks)==len(expected_sannysoft) and {n.replace('\n',' ') for n,c in checks}==expected_sannysoft,(p,'Sannysoft recognized check schema changed')
    out['failed']=[n.replace('\n',' ') for n,c in observed if 'failed' in c.split()]
    out['warn']=[n.replace('\n',' ') for n,c in observed if 'warn' in c.split()]
    out['stable_6_to_10s']=states(old)==observed
   row[name]=out
  else:row[name]=out
 rows.append(row)
if args.require_complete:
 assert len(rows)==28 and {r['key'] for r in rows}==expected_keys,'Incomplete run matrix'
 for row in rows:
  assert not row.get('launch_error'),(row['key'],'launch error')
  assert row.get('local_properties'),(row['key'],'missing local capture')
  sites=['browserscan']+(['sannysoft'] if row['repetition']==1 else [])
  for site in sites:
   assert site in row and not row[site].get('error'),(row['key'],site,'missing/invalid capture')
   assert (ROOT/row[site]['screenshot']).is_file(),(row['key'],site,'missing screenshot')
 assert sum('browserscan' in r for r in rows)==28 and sum('sannysoft' in r for r in rows)==14,'Unexpected suite coverage'
(ROOT/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:
 b=r.get('browserscan',{});s=r.get('sannysoft',{})
 print(r['key'],r.get('browser_version'),r.get('launch_error') or b.get('error') or f"{b.get('verdict')} [{','.join(b.get('flagged',[]))}]",'Sannysoft:',s.get('error') or (','.join(s.get('failed',[])) or 'none') if s else 'not repeated', 'stable:',b.get('stable_6_to_10s'))
