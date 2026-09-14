"""Fixture locations shared by the examples."""
from pathlib import Path

HERE = Path(__file__).parent / "fixtures"
LOCAL = {
    "domcontentloaded": (HERE / "dynamic-domcontentloaded.html").resolve(),
    "delayed": (HERE / "dynamic-delayed.html").resolve(),
}
PUBLIC = {
    "domcontentloaded": "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-domcontentloaded.html",
    "delayed": "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html",
}
