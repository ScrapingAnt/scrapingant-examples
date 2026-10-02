"""Render programmatic charts and exact saved-output extracts; no network/API calls."""
import csv
import html as escape
import json
from pathlib import Path
from lxml import html
from playwright.sync_api import sync_playwright
from score import analyze

ROOT=Path(__file__).resolve().parent
records=[json.loads(x) for x in (ROOT/'data/captures.jsonl').read_text().splitlines()]
rows,summary=analyze(records)
css='''*{box-sizing:border-box}body{margin:0;background:#f7f9fa;color:#173042;font-family:Arial,sans-serif}main{padding:32px;width:760px}h1{font-size:36px;line-height:1.15;margin:0 0 12px}h2{font-size:30px;margin:0 0 18px}.note{font-size:25px;line-height:1.35;color:#465c69;margin:12px 0 26px}.panel{background:white;border:2px solid #c9d6de;border-radius:14px;padding:26px;margin:18px 0}.output{font-size:32px;line-height:1.45}.small{font-size:25px}.badge{font-size:26px;font-weight:bold;color:#196447;margin:22px 0 0}pre{font:25px/1.5 monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}table{border-collapse:collapse;width:100%;font-size:29px}th,td{border:2px solid #b7c8d3;padding:14px;text-align:center}th{background:#e6f2eb}'''
def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>'+title+'</title><style>'+css+'</style><main>'+body+'</main></html>'

def lookup(kind,pos):
    return next(r for r in records if r['unit_type']==kind and r['pair_position']==pos)
first=lookup('delayed-corrective-pair',1); second=lookup('delayed-corrective-pair',2)
body='<h1>HTTP 200 can still be a placeholder</h1><p class="note">Exact saved HTML, rendered offline with display styling.</p>'
for r,label,verdict in [(first,'Default wait (omitted)','Rendered-content contract: FAIL'),(second,'waitFor: 2500 ms','Rendered-content contract: PASS')]:
    fragment=html.fromstring(r['html']); content=''.join(html.tostring(c,encoding='unicode') for c in fragment.xpath('//body/*'))
    body+=f'<section class="panel"><h2>{label}</h2><p class="small">Saved output {r["sequence"]} · target status 200 · 1 credit</p><div class="output">{content}</div><p class="badge">{verdict}</p></section>'
body+='<p class="note">Fixture changes its DOM after 1,500 ms. This is one controlled page.</p>'
(ROOT/'visuals/delayed-render.html').write_text(page('Delayed output evidence',body))
table_record=next(r for r in records if r['phase']=='expansion' and r['fixture']=='html-tables' and r['params']['onlyMainContent'])
tree=html.fromstring(table_record['html']); table=tree.xpath('//table[@id="two-row-header"]')[0]
lines=table_record['markdown'].splitlines(); start=next(i for i,l in enumerate(lines) if l.startswith('## 3')); end=next(i for i,l in enumerate(lines[start+1:],start+1) if l.startswith('## 4'))
md='\n'.join(lines[start+1:end]).strip()
body=f'<h1>One table, two representations</h1><p class="note">Saved output {table_record["sequence"]} · exact two-row-header extract</p><section class="panel"><h2>Returned HTML, rendered</h2>{html.tostring(table,encoding="unicode")}<p class="small">Region spans two header rows. Each year spans Q1 and Q2.</p></section><section class="panel"><h2>Returned Markdown, exact text</h2><pre>{escape.escape(md)}</pre><p class="small">Pipe rows have unequal cell counts. Reconstruct year/quarter labels before ingesting.</p></section><p class="note">Presentation CSS added. No cells, values or pipe delimiters changed.</p>'
(ROOT/'visuals/table-render.html').write_text(page('Table output evidence',body))
chart=[]
for name,label,contract in [('complete-catalog','Complete catalog','basic'),('delayed-js-wait-2500','Delayed content, wait 2500','basic')]:
    rs=[r for r in rows if r['unit_type']=='independent' and r['setting']==name]
    chart.append({'subset':label,'credits':sum(r['credits'] for r in rs),'accepted':sum(r['basic_preservation'] for r in rs)})
for p,label in zip(summary['pairs'][:2],['Corrective retry pairs','Same-setting retry pairs']):
    chart.append({'subset':label,'credits':p['credits'],'accepted':p['accepted_delayed_outputs']})
with (ROOT/'visuals/credits-data.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['subset','credits','accepted']);w.writeheader();w.writerows(chart)
body='<h1>Credits per accepted output</h1><p class="note">Observed credits, not measured cash. Distinct application contracts.</p>'
for r in chart:
    ratio=r['credits']/r['accepted'] if r['accepted'] else None
    bar=f'<div style="height:30px;background:#29805c;width:{ratio/2*100}%"></div>' if ratio else '<div style="border:2px dashed #b77735;padding:8px;font-size:27px">Undefined: zero accepted</div>'
    text=f'{ratio:g} credit' + (' each' if ratio==1 else 's each') if ratio else 'Ratio undefined'
    body+=f'<section class="panel"><h2>{r["subset"]}</h2><p class="small">{r["credits"]} credits ÷ {r["accepted"]} accepted · {text}</p>{bar}</section>'
body+='<p class="note">Retry pairs include both billed calls. First failures stay in the numerator.</p>'
(ROOT/'visuals/credits-render.html').write_text(page('Accepted output costs',body))
# Banner is editorial artwork, not a study screenshot.
(ROOT/'visuals/banner-render.html').write_text('<!doctype html><html><meta charset="utf-8"><style>body{margin:0;background:#153347;color:#fff;font-family:Arial}main{box-sizing:border-box;width:1200px;height:630px;padding:72px}h1{font-size:76px;line-height:1.05;width:1000px;margin:50px 0 30px}p{font-size:34px;color:#b9dccc}.brand{font-size:26px;color:#92c7af;letter-spacing:4px}strong{color:#77d8ab}</style><main><div class="brand">SCRAPINGANT · PRICING GUIDE</div><h1>Firecrawl pricing:<br><strong>budget for accepted results</strong></h1><p>Plan prices · credit consumption · modeled bills</p></main></html>')
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    context=b.new_context(viewport={'width':760,'height':1000},device_scale_factor=2)
    context.route('**/*',lambda route:route.abort() if route.request.url.startswith(('http:','https:')) else route.continue_())
    tab=context.new_page()
    for slug in ['credits','delayed','table','banner']:
        tab.set_viewport_size({'width':1200 if slug=='banner' else 760,'height':630 if slug=='banner' else 1000})
        tab.set_content((ROOT/f'visuals/{slug}-render.html').read_text())
        tab.locator('main').screenshot(path=str(ROOT/f'visuals/{slug}.png'),scale='css' if slug=='banner' else 'device')
    print('Rendered three evidence visuals and editorial banner with Chromium '+b.version)
    b.close()
