from xml.dom import minidom
import xml.sax, xml.parsers.expat

doc = minidom.parse("fixtures/books.xml")
titles = doc.getElementsByTagName("title")
print("minidom:", len(titles), [t.firstChild.data for t in titles])
print(doc.getElementsByTagName("book")[0].getAttribute("id"), doc.documentElement.tagName)

class Handler(xml.sax.ContentHandler):
    def __init__(self): self.count = {}; self.path = []
    def startElement(self, name, attrs): self.count[name] = self.count.get(name, 0) + 1
xml_handler = Handler(); xml.sax.parse("fixtures/books.xml", xml_handler)
print("sax element counts:", xml_handler.count)

p = xml.parsers.expat.ParserCreate(); seen = []
p.StartElementHandler = lambda name, attrs: seen.append((name, attrs.get("id")) if name == "book" else None)
with open("fixtures/books.xml", "rb") as f: p.ParseFile(f)
print("expat books:", [s for s in seen if s])
