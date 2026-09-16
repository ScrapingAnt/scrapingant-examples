import xml.etree.ElementTree as ET

tree = ET.parse("fixtures/books.xml")
root = tree.getroot()
print(root.tag, root.attrib)
for book in root.findall("book"):
    print(book.get("id"), book.find("title").text, book.findtext("price", default="n/a"))

# attributes and text of a nested element
first = root.find("book")
print(first.find("price").attrib, first.find("price").text)
# every <tag> anywhere below root
print([t.text for t in root.iter("tag")])
# a path: books whose id is bk103, then the CDATA description
print(root.find("book[@id='bk103']/description").text)
# missing element -> None, not an exception
print(root.find("book/isbn"))
# the same from bytes (what requests gives you) and from a str
data = open("fixtures/books.xml", "rb").read()
print(ET.fromstring(data).tag, ET.fromstring("<a><b>x</b></a>").find("b").text)
