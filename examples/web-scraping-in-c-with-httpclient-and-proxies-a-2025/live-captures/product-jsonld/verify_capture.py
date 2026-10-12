"""Replay immutable owned source and actual native-client capture; zero requests/key reads."""
import copy
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
PRODUCT = {"sku": "SYNTH-000", "title": "Synthetic product 000", "price": Decimal("12.34"), "currency": "USD"}
SOURCE_HASH = "7c091cea8ce4b224709e8cc978a79b0c51d7294b68d62afd538d887bc7d43dcd"
RESPONSE_HASH = "169b93ff2cfc5e750ae4cfe1f209766a63beb2f1d0d4eddc32fe7b8945d73695"
FIELDS = {"phase", "scope", "started_utc", "finished_utc", "latency_ms", "dispatches", "outer_status",
          "target_status", "actual_receipt_credits", "original_target_type", "outer_type", "body_bytes",
          "body_sha256", "client_returned", "full_public_client_validated", "client_attempts", "product",
          "body_saved", "accepted", "failure", "public_cli_executed", "real_store_validated", "receipt_saved", "requests"}


def require(condition, message):
    if not condition: raise ValueError(message)


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.active = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script": self.active = False

    def handle_data(self, data):
        if self.active: self.scripts[-1] += data


def script(body):
    parser = Scripts()
    parser.feed(body.decode("utf-8"))
    require(len(parser.scripts) == 1, "Native script cardinality differs")
    return parser.scripts[0]


def verify(receipt, body, source, source_receipt, oracle):
    require(set(receipt) == FIELDS, "Receipt fields differ from allowlist")
    require(len(body) == 601 == receipt["body_bytes"], "Managed body size differs")
    require(hashlib.sha256(body).hexdigest() == RESPONSE_HASH == receipt["body_sha256"], "Managed body hash differs")
    require(len(source) == 588 == source_receipt["body_bytes"], "Source entity size differs")
    require(hashlib.sha256(source).hexdigest() == SOURCE_HASH == source_receipt["body_sha256"], "Source hash differs")
    require(source_receipt["status"] == 200 and source_receipt["matches_local_fixture"] is True, "Owned source gate differs")
    require(receipt["scope"] == "owned-single-product-jsonld-integrated-fetch", "Capture scope differs")
    require(receipt["requests"] == receipt["dispatches"] == receipt["client_attempts"] == 1, "One-attempt count differs")
    require(type(receipt["actual_receipt_credits"]) is int and receipt["actual_receipt_credits"] == 10, "Actual receipt differs or is unknown")
    require(receipt["outer_status"] == receipt["target_status"] == 200, "Observed statuses differ")
    require(receipt["original_target_type"] == receipt["outer_type"] == "text/html", "Observed media types differ")
    require(all(receipt[name] is True for name in ("accepted", "client_returned", "full_public_client_validated", "body_saved", "receipt_saved")), "Acceptance flags differ")
    require(receipt["failure"] is None and receipt["public_cli_executed"] is False and receipt["real_store_validated"] is False, "Unvalidated scope was broadened")
    require(receipt["product"] == PRODUCT == oracle, "Literal four-field product differs")
    require(script(source) == script(body), "Native JSON-LD script differs from owned source")
    native = json.loads(script(body))
    require(native["@context"] == "https://schema.org" and native["@type"] == "Product" and native["offers"]["@type"] == "Offer", "Native Product/Offer contract differs")
    require(type(native["offers"]["price"]) is str, "Native price is not the observed string")
    parsed = {"sku": native["sku"], "title": native["name"], "price": Decimal(native["offers"]["price"]), "currency": native["offers"]["priceCurrency"]}
    require(parsed == PRODUCT, "Native script fields differ from literals")


def inputs():
    return (json.loads((ROOT / "receipt.json").read_text(), parse_float=Decimal),
            (ROOT / "response.html").read_bytes(), (ROOT / "source-response.html").read_bytes(),
            json.loads((ROOT / "source-receipt.json").read_text()),
            json.loads((ROOT / "oracle.json").read_text(), parse_float=Decimal))


class Controls(unittest.TestCase):
    def reject(self, mutate):
        values = list(copy.deepcopy(inputs()))
        mutate(values)
        with self.assertRaises(ValueError): verify(*values)

    def test_body_bytes(self): self.reject(lambda v: v.__setitem__(1, v[1] + b"x"))
    def test_wrong_receipt(self): self.reject(lambda v: v[0].update(actual_receipt_credits=0))
    def test_unknown_receipt(self): self.reject(lambda v: v[0].update(actual_receipt_credits=None))
    def test_wrong_price(self): self.reject(lambda v: v[0]["product"].update(price=0))
    def test_wrong_sku(self): self.reject(lambda v: v[0]["product"].update(sku="OTHER"))
    def test_false_client_flag(self): self.reject(lambda v: v[0].update(full_public_client_validated=False))
    def test_false_cli_claim(self): self.reject(lambda v: v[0].update(public_cli_executed=True))
    def test_false_store_claim(self): self.reject(lambda v: v[0].update(real_store_validated=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--controls"]:
        result = unittest.TextTestRunner(stream=sys.stdout).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        if not result.wasSuccessful(): raise SystemExit(1)
        print("PASS 8/8 saved native-capture corruption controls")
    else:
        verify(*inputs())
        print("PASS 1/1 saved native full-client capture: exact four fields, hashes, statuses and actual 10-credit receipt; replay API calls=0")
