"""Wall time and peak memory per approach on a generated file, each approach in its own process."""
import os, resource, subprocess, sys, time

def generate(path, n):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<records>\n')
            for i in range(n):
                f.write(f'  <record id="{i}" region="{"eu" if i % 3 else "us"}"><name>Item {i}</name><price currency="USD">{i % 1000}.{i % 100:02d}</price><stock>{i % 7}</stock></record>\n')
            f.write("</records>\n")
    return os.path.getsize(path) / 1e6

N = 200_000
PATH = "generated/large.xml"
size_mb = generate(PATH, N)

APPROACHES = {
    "ET.parse + findall": "import xml.etree.ElementTree as ET; r=ET.parse(P).getroot(); n=sum(1 for e in r.findall('record') if e.get('region')=='us')",
    "ET.iterparse + clear": "import xml.etree.ElementTree as ET; n=0\nfor ev,e in ET.iterparse(P):\n    if e.tag=='record':\n        n+= e.get('region')=='us'; e.clear()",
    "ET.iterparse + clear + root.clear": "import xml.etree.ElementTree as ET; n=0; it=ET.iterparse(P, events=('start','end')); _, root=next(it)\nfor ev,e in it:\n    if ev=='end' and e.tag=='record':\n        n+= e.get('region')=='us'; e.clear(); root.clear()",
    "lxml.parse + xpath": "from lxml import etree; n=int(etree.parse(P).xpath(\"count(//record[@region='us'])\"))",
    "lxml.iterparse + clear": "from lxml import etree; n=0\nfor ev,e in etree.iterparse(P, tag='record'):\n    n+= e.get('region')=='us'; e.clear()\n    while e.getprevious() is not None: del e.getparent()[0]",
    "xml.sax handler": "import xml.sax\nclass H(xml.sax.ContentHandler):\n    n=0\n    def startElement(s,name,a):\n        if name=='record' and a.get('region')=='us': s.n+=1\nh=H(); xml.sax.parse(P,h); n=h.n",
    "xml.dom.minidom": "from xml.dom import minidom; d=minidom.parse(P); n=sum(1 for e in d.getElementsByTagName('record') if e.getAttribute('region')=='us')",
    "xmltodict.parse": "import xmltodict; d=xmltodict.parse(open(P,'rb').read()); n=sum(1 for r in d['records']['record'] if r['@region']=='us')",
    "untangle.parse": "import untangle; o=untangle.parse(P); n=sum(1 for r in o.records.record if r['region']=='us')",
    "BeautifulSoup(features='xml')": "from bs4 import BeautifulSoup; s=BeautifulSoup(open(P,'rb').read(), features='xml'); n=sum(1 for r in s.find_all('record') if r.get('region')=='us')",
}
def run_table(path, size_mb, n_records, names):
    print(f"file: {path}, {size_mb:.1f} MB, {n_records:,} <record> elements; task: count records with region=\"us\"; one subprocess per approach")
    print(f"{'approach':32} {'seconds':>8} {'peak RSS MB':>12} {'count':>8}")
    for name in names:
        code = APPROACHES[name]
        prog = f"import resource,sys,time\nP={path!r}\nt=time.perf_counter()\n{code}\nprint(n, round(time.perf_counter()-t,2), round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024*1024 if sys.platform=='darwin' else 1024)))"
        out = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, timeout=900)
        if out.returncode:
            print(f"{name:32} failed: {out.stderr.strip().splitlines()[-1][:80]}"); continue
        n, secs, mb = out.stdout.split()
        print(f"{name:32} {float(secs):8.2f} {int(mb):12d} {int(n):8d}")

run_table(PATH, size_mb, N, list(APPROACHES))
# twice the file: does streaming memory grow with the file, does a tree?
print()
N2 = 400_000; PATH2 = "generated/large2.xml"
run_table(PATH2, generate(PATH2, N2), N2, ["ET.parse + findall", "ET.iterparse + clear", "ET.iterparse + clear + root.clear", "lxml.parse + xpath", "lxml.iterparse + clear", "xml.sax handler"])
