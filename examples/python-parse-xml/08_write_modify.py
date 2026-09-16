import xml.etree.ElementTree as ET

tree = ET.parse("fixtures/books.xml"); root = tree.getroot()
book = root.find("book[@id='bk103']")
book.set("lang", "en"); book.find("title").text = "Maeve Ascendant (2nd ed.)"
price = ET.SubElement(book, "price", currency="EUR"); price.text = "9.99"
root.remove(root.find("book[@id='bk102']"))
ET.indent(root, space="  ")
tree.write("generated/books-modified.xml", encoding="utf-8", xml_declaration=True)
print(open("generated/books-modified.xml", encoding="utf-8").read())

new = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
for loc in ("https://example.com/", "https://example.com/a"):
    u = ET.SubElement(new, "url"); ET.SubElement(u, "loc").text = loc
ET.indent(new)
print(ET.tostring(new, encoding="unicode"))
