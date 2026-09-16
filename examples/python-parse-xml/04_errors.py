import xml.etree.ElementTree as ET
from lxml import etree
from _common import show

show("ET.parse('fixtures/broken.xml')", lambda: ET.parse("fixtures/broken.xml"))
try:
    ET.parse("fixtures/broken.xml")
except ET.ParseError as e:
    print("ParseError.position (line, column):", e.position)
show("etree.parse('fixtures/broken.xml')", lambda: etree.parse("fixtures/broken.xml"))
try:
    etree.parse("fixtures/broken.xml")
except etree.XMLSyntaxError as e:
    print("XMLSyntaxError.lineno:", e.lineno, "error_log entries:", len(e.error_log))
recovered = etree.parse("fixtures/broken.xml", etree.XMLParser(recover=True))
print("recover=True:", etree.tostring(recovered.getroot()).decode())
show("ET.parse('fixtures/missing.xml')", lambda: ET.parse("fixtures/missing.xml"))
