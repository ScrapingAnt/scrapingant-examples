import xml.etree.ElementTree as ET, pyexpat
from lxml import etree
import defusedxml.ElementTree as DET
from _common import show

print("expat", pyexpat.EXPAT_VERSION, "| libxml2", ".".join(map(str, etree.LIBXML_VERSION)))
BL, XXE = "fixtures/billion-laughs.xml", "fixtures/xxe.xml"
show("ET.parse(billion-laughs)", lambda: len(ET.parse(BL).getroot().text))
show("ET.parse(xxe)", lambda: ET.parse(XXE).getroot().text)
show("etree.parse(billion-laughs) default parser", lambda: len(etree.parse(BL).getroot().text))
show("etree.parse(xxe) default parser", lambda: etree.parse(XXE).getroot().text)
show("etree.parse(xxe, XMLParser(resolve_entities=True))", lambda: etree.parse(XXE, etree.XMLParser(resolve_entities=True)).getroot().text)
show("etree.parse(xxe, XMLParser(resolve_entities=False))", lambda: etree.parse(XXE, etree.XMLParser(resolve_entities=False)).getroot().text)
show("etree.parse(billion-laughs, XMLParser(huge_tree=True))", lambda: len(etree.parse(BL, etree.XMLParser(huge_tree=True)).getroot().text))
show("defusedxml.ElementTree.parse(billion-laughs)", lambda: DET.parse(BL))
show("defusedxml.ElementTree.parse(xxe)", lambda: DET.parse(XXE))
show("defusedxml.ElementTree.parse(books.xml)", lambda: DET.parse("fixtures/books.xml").getroot().tag)
