"""Literal oracles catch misassignment; wholly owned bytes exercise rejection."""
import copy
import json
from pathlib import Path
import unittest
import collector

ROOT = Path(__file__).parent
SOURCE = "https://scrapingant.github.io/scrapingant-examples/examples/retail-shelf-intelligence-scraping-digital-shelves-for-cpg/fixtures/baseline.html"
NOW = "2026-10-13T11:00:00Z"

def fixture():
    return (ROOT / "fixtures/baseline.html").read_bytes()

def parse(body=None, source=SOURCE, time=NOW):
    return collector.parse_page(fixture() if body is None else body, requested_source_url=source, observed_at_utc=time)

class Records(unittest.TestCase):
    def test_selected_offers_match_independent_literal_oracle(self):
        actual = parse()
        expected = json.loads((ROOT / "fixtures/baseline-records.json").read_text())
        self.assertEqual(actual["records"], expected)
        self.assertTrue(actual["complete"])
        self.assertEqual(actual["rejected"], [])

    def test_aggregate_from_price_is_not_a_selected_weight_price(self):
        records = parse()["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual([r["price"] for r in records], ["8.25", "24.00"])

    def test_shared_URL_does_not_merge_variants_or_invent_variant_ID(self):
        records = parse()["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual([r["sku"] for r in records], ["000701002", "000701004"])
        self.assertEqual([r["variant_id"] for r in records], [None, None])
        self.assertEqual(records[0]["observed_source_url"], records[1]["observed_source_url"])

    def test_explicit_OOS_and_unknown_remain_distinct(self):
        records = parse()["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["availability"], "out_of_stock")
        for replacement in (b'', b',"availability":"https://schema.org/PreOrder"'):
            body = fixture().replace(b',"availability":"https://schema.org/OutOfStock"', replacement)
            self.assertEqual(parse(body)["records"][1]["availability"], "unknown")

    def test_missing_price_keeps_other_variant_and_marks_partial(self):
        result = parse(fixture().replace(b'"price":"8.25",', b''))
        self.assertFalse(result["complete"])
        self.assertEqual([r["sku"] for r in result["records"]], ["000701004"])
        self.assertEqual(result["rejected"], [{"sku":"000701002", "reason":"invalid_price"}])

    def test_missing_currency_cannot_be_inferred_from_aggregate(self):
        result = parse(fixture().replace(b'"price":"8.25","priceCurrency":"USD"', b'"price":"8.25"'))
        self.assertFalse(result["complete"])
        self.assertEqual([r["sku"] for r in result["records"]], ["000701004"])

    def test_wrong_SKU_does_not_fill_the_selected_slot(self):
        result = parse(fixture().replace(b'000701002', b'999701002'))
        self.assertFalse(result["complete"])
        self.assertEqual([r["sku"] for r in result["records"]], ["000701004"])

    def test_wrong_group_preserving_leading_zeroes_is_rejected(self):
        self.assertEqual(parse(fixture().replace(b'"000701"', b'"701"'))["records"], [])

    def test_pack_label_is_narrow_and_weight_not_count(self):
        for bad in (b'3g', b'3 x 2oz', b'0oz', b'999999999oz', b'3.5oz'):
            with self.subTest(bad=bad):
                result = parse(fixture().replace(b'3oz', bad))
                self.assertFalse(result["complete"])
                self.assertEqual(len(result["records"]), 1)

    def test_bad_decimal_price_is_rejected(self):
        for bad in (b'"NaN"', b'"-1.00"', b'"1,000.00"', b'true', b'"1.001"'):
            with self.subTest(bad=bad):
                result = parse(fixture().replace(b'"8.25"', bad))
                self.assertFalse(result["complete"])
                self.assertEqual(len(result["records"]), 1)

    def test_numeric_price_uses_decimal_not_binary_float(self):
        records = parse(fixture().replace(b'"8.25"', b'8.10'))["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["price"], "8.10")

    def test_currency_is_explicit_USD_not_dollar_inference(self):
        for bad in (b'""', b'"EUR"', b'"US"', b'null'):
            with self.subTest(bad=bad):
                self.assertEqual(parse(fixture().replace(b'"USD"', bad))["records"], [])

    def test_wrong_source_canonical_group_and_offer_cannot_accept(self):
        self.assertEqual(parse(source=SOURCE + "?different=1")["records"], [])
        self.assertEqual(parse(fixture().replace(b'scrapingant.github.io', b'evil.example'))["records"], [])
        body = fixture().replace(b'"url":"' + SOURCE.encode() + b'","price":"8.25"', b'"url":"https://evil.example/","price":"8.25"')
        self.assertEqual([r["sku"] for r in parse(body)["records"]], ["000701004"])

    def test_UTC_observation_is_calendar_valid_not_a_source_date(self):
        for bad in ("2026-10-13", "2026-02-30T11:00:00Z", "2026-10-13T11:00:00+02:00", "not-a-time"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse(time=bad)

    def test_missing_page_is_failed_not_complete_empty_inventory(self):
        for body in (b'', b'<html><body>Access denied</body></html>', b'{"message":"error"}'):
            with self.subTest(body=body):
                result = parse(body)
                self.assertEqual(result["records"], [])
                self.assertFalse(result["complete"])

    def test_duplicate_JSON_keys_are_ambiguous(self):
        self.assertEqual(parse(fixture().replace(b'"productGroupID":', b'"productGroupID":"wrong","productGroupID":'))["records"], [])

    def test_duplicate_group_is_ambiguous(self):
        body = fixture()
        block = body[body.index(b'<script'):body.index(b'</script>') + 9]
        self.assertEqual(parse(body.replace(b'</main>', block + b'</main>'))["records"], [])

    def test_duplicate_and_conflicting_selected_SKU_excludes_both(self):
        body = fixture()
        start = body.index(b'{"@type":"Product","sku":"000701002"')
        end = body.index(b'\n', start)
        product = body[start:end].rstrip(b',')
        for duplicate in (product, product.replace(b'"8.25"', b'"9.25"')):
            with self.subTest(conflict=duplicate != product):
                result = parse(body.replace(b']}</script>', b',' + duplicate + b']}</script>'))
                self.assertFalse(result["complete"])
                self.assertEqual([r["sku"] for r in result["records"]], ["000701004"])

    def test_two_variant_offers_are_ambiguous(self):
        body = fixture().replace(b'"offers":{"@type":"Offer","url":"' + SOURCE.encode() + b'","price":"8.25"', b'"offers":[{"@type":"Offer","url":"' + SOURCE.encode() + b'","price":"8.25"').replace(b'"availability":"https://schema.org/InStock"}},\n{"@type":"Product","sku":"000701004"', b'"availability":"https://schema.org/InStock"}],\n{"@type":"Product","sku":"000701004"')
        self.assertFalse(parse(body)["complete"])

    def test_oversized_HTML_is_rejected_before_parsing(self):
        self.assertEqual(parse(fixture() + b' ' * 262145)["records"], [])

    def test_market_is_observed_page_context_not_currency_or_proxy(self):
        self.assertEqual([r["market"] for r in parse()["records"]], ["unknown","unknown"])
        inside = b'<div itemprop="shippingDestination"><meta itemprop="addressCountry" content="US" /></div>'
        actual = parse(fixture().replace(b'</main>', inside + b'</main>'))
        self.assertEqual([r["market"] for r in actual["records"]], ["US","US"])
        self.assertEqual([r["fulfilment"] for r in actual["records"]], ["unselected","unselected"])
        outside = b'<meta itemprop="addressCountry" content="US" />'
        self.assertEqual([r["market"] for r in parse(fixture().replace(b'</main>', outside + b'</main>'))["records"]], ["unknown","unknown"])

    def test_wrong_type_and_truncated_JSON_are_failed_not_empty_inventory(self):
        for body in (fixture().replace(b'"hasVariant":[', b'"hasVariant":false,"ignored":['),
                     fixture().replace(b'"sku":"000701002"', b'"sku":["000701002"]'),
                     fixture()[:900], fixture().replace(b']}</script>', b']')):
            with self.subTest(length=len(body)):
                self.assertFalse(parse(body)["complete"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
