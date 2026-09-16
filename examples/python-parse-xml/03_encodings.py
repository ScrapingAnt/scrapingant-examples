import xml.etree.ElementTree as ET
from lxml import etree
from _common import show

show("ET.parse('fixtures/latin1.xml') (bytes, declaration honoured)", lambda: ET.parse("fixtures/latin1.xml").getroot().find("to").text)
show("ET.fromstring(open(..., 'rb').read())", lambda: ET.fromstring(open("fixtures/latin1.xml", "rb").read()).find("body").text)
show("open(..., encoding='utf-8').read() then ET.fromstring", lambda: ET.fromstring(open("fixtures/latin1.xml", encoding="utf-8").read()).find("to").text)
show("open(..., encoding='latin-1').read() then ET.fromstring", lambda: ET.fromstring(open("fixtures/latin1.xml", encoding="latin-1").read()).find("to").text)
show("etree.fromstring(str with declaration)", lambda: etree.fromstring(open("fixtures/latin1.xml", encoding="latin-1").read()).find("to").text)
show("etree.fromstring(bytes)", lambda: etree.fromstring(open("fixtures/latin1.xml", "rb").read()).find("to").text)
