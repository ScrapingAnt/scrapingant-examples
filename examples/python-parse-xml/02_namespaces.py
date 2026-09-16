import xml.etree.ElementTree as ET

root = ET.parse("fixtures/sitemap.xml").getroot()
print("root.tag:", root.tag)
print("findall('url'):", root.findall("url"))                        # empty: the elements are in a namespace

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
print("1 braces:", [u.find(NS + "loc").text for u in root.findall(NS + "url")])

ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "xhtml": "http://www.w3.org/1999/xhtml"}
print("2 prefix map:", [u.findtext("sm:loc", namespaces=ns) for u in root.findall("sm:url", ns)])

print("3 wildcard:", [u.findtext("{*}loc") for u in root.findall("{*}url")])

# lastmod only where present; alternates via the second namespace
for u in root.findall("sm:url", ns):
    alt = u.find("xhtml:link", ns)
    print(u.findtext("sm:loc", namespaces=ns), u.findtext("sm:lastmod", namespaces=ns), alt.get("hreflang") if alt is not None else None)

# register the prefix so serialised output keeps it instead of ns0
ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
ET.register_namespace("xhtml", "http://www.w3.org/1999/xhtml")
print(ET.tostring(root.find("sm:url", ns), encoding="unicode").strip().splitlines()[0])
