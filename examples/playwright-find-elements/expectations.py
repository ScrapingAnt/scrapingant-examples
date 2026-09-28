"""Literal wrong-control outcomes and intended record subsets; never imported by fixture."""
from oracle import CATALOG, DECOY, FRAME, PENDING, SHADOW


def expected_cases():
    return {
        "strict_duplicate": {"outcome": "strict_mode_violation", "matched_skus": ["AD-000", "K-101", "M-202", "T-303"]},
        "first_masks_decoy": {"records": DECOY},
        "eager_count_all": {"state": "loading", "count": 1, "all_length": 1, "records": PENDING},
        "scoped_records": {"records": CATALOG},
        "locator_reresolution": {"before": "Copper Kettle (archived)", "after": "Copper Kettle", "same_dom_node": False, "records": CATALOG},
        "evaluate_all": {"records": CATALOG},
        "role_records": {"records": CATALOG},
        "text_exact": {"ancestor_prefixed_skus": [], "records": [CATALOG[1]]},
        "css_attribute": {"records": [CATALOG[0]]},
        "xpath_records": {"records": CATALOG},
        "frame_scope": {"top_document_skus": ["AD-000", "K-101", "M-202", "T-303"], "records": FRAME},
        "shadow_scope": {"locator_skus": ["S-505"], "raw_document_skus": ["AD-000", "K-101", "M-202", "T-303"], "xpath_skus": [], "records": SHADOW},
    }


def expected_diagnostics():
    return {
        "missing_selector": {"outcome": "TimeoutError", "selector": "#never-present"},
        "text_readers": {"inner_text": "Tea & Honey", "text_content": "Tea & HoneyHIDDEN"},
        "attribute_property": {"attribute_href": "/products/kettle", "property_href": "{origin}/products/kettle", "optional_present": "featured", "optional_missing": None},
        "query_semantics": {"role_visible": ["Visible offer"], "role_include_hidden": ["Visible offer", "Hidden offer"], "text_normalized": ["whitespace"], "css": ["offer-visible", "offer-hidden"], "xpath": ["offer-visible", "offer-hidden"]},
    }
