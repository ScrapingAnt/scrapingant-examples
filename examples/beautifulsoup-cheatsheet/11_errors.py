import subprocess, sys, tempfile
from bs4 import BeautifulSoup
from _common import PAGE, show
soup = BeautifulSoup(PAGE, "html.parser")
show("soup.find('p', class_='discount').text", lambda: soup.find("p", class_="discount").text)
tag = soup.find("p", class_="discount")
print(tag.text if tag else "no discount")
show("soup.select_one('p.discount').get_text()", lambda: soup.select_one("p.discount").get_text())
print(soup.select_one("p.discount").get_text() if soup.select_one("p.discount") else "no discount")
# FeatureNotFound: an environment with beautifulsoup4 but no lxml (bs4 installed into a scratch dir, site-packages hidden)
d = tempfile.mkdtemp()
installer = [sys.executable, "-m", "pip", "install", "-q", "--target", d, "beautifulsoup4==4.15.0"]
if subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode:
    installer = ["uv", "pip", "install", "-q", "--target", d, "beautifulsoup4==4.15.0"]
subprocess.run(installer, check=True, capture_output=True)
code = f"import sys; sys.path = [{d!r}] + [p for p in sys.path if 'site-packages' not in p]\nfrom bs4 import BeautifulSoup\ntry:\n    BeautifulSoup('<p>x</p>', 'lxml')\nexcept Exception as e:\n    print(type(e).__name__ + ': ' + str(e))\nprint(BeautifulSoup('<p>x</p>', 'html.parser').p.string)"
print(subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True).stdout.strip())
