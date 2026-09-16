from lxml import etree

tree = etree.parse("fixtures/books.xml")
print("xpath titles:", tree.xpath("//book[@lang='en']/title/text()"))
print("xpath count:", tree.xpath("count(//book)"), "sum prices:", tree.xpath("sum(//price)"))
print("xpath attr:", tree.xpath("//book[price > 10]/@id"))
print("sourceline of bk102:", tree.xpath("//book[@id='bk102']")[0].sourceline)

# namespaces in XPath need a prefix map
sm = etree.parse("fixtures/sitemap.xml")
ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "xhtml": "http://www.w3.org/1999/xhtml"}
print("sitemap locs:", sm.xpath("//sm:url/sm:loc/text()", namespaces=ns))
print("alternates:", sm.xpath("//xhtml:link/@href", namespaces=ns))

# iterparse with clearing: the pattern for big files
seen = []
for event, elem in etree.iterparse("fixtures/books.xml", tag="book"):
    seen.append(elem.get("id")); elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]
print("iterparse books:", seen)

# schema validation
schema = etree.XMLSchema(etree.parse("fixtures/books.xsd"))
print("books.xml valid:", schema.validate(etree.parse("fixtures/books.xml")))
bad = etree.parse("fixtures/books-invalid.xml")
print("books-invalid.xml valid:", schema.validate(bad))
print("first error:", schema.error_log.filter_from_errors()[0].message)
try:
    etree.parse("fixtures/books-invalid.xml", etree.XMLParser(schema=schema))
except etree.XMLSyntaxError as e:
    print("XMLParser(schema=...):", type(e).__name__, str(e).rsplit(" (", 1)[0])

# pretty print
print(etree.tostring(tree.xpath("//book[@id='bk102']")[0], pretty_print=True).decode().strip())
