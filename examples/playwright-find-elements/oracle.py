"""Literal record expectations, independent of HTML fixture construction."""
CATALOG = [
    {"sku": "K-101", "title": "Copper Kettle", "currency": "USD", "price": "24.50", "href": "/products/kettle"},
    {"sku": "M-202", "title": "Café Mug", "currency": "EUR", "price": "12.00", "href": "/products/mug"},
    {"sku": "T-303", "title": "Tea & Honey", "currency": "GBP", "price": "8.75", "href": "/products/tea"},
]
DECOY = [{"sku": "AD-000", "title": "Sponsored kettle", "currency": "USD", "price": "999.00", "href": "/ads/kettle"}]
PENDING = [{"sku": "PENDING", "title": "Loading catalog", "currency": "XXX", "price": "0.00", "href": "/pending"}]
FRAME = [{"sku": "F-404", "title": "Frame spoon", "currency": "USD", "price": "3.25", "href": "/products/spoon"}]
SHADOW = [{"sku": "S-505", "title": "Shadow strainer", "currency": "EUR", "price": "6.50", "href": "/products/strainer"}]
CASE_IDS = (
    "strict_duplicate", "first_masks_decoy", "eager_count_all", "scoped_records",
    "locator_reresolution", "evaluate_all", "role_records", "text_exact",
    "css_attribute", "xpath_records", "frame_scope", "shadow_scope",
)
DIAGNOSTIC_IDS = ("missing_selector", "text_readers", "attribute_property", "query_semantics")


def validate_records(records, expected):
    import re
    fields = {"sku", "title", "currency", "price", "href"}
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a nonempty list")
    for record in records:
        if not isinstance(record, dict) or set(record) != fields:
            raise ValueError("record fields differ from schema")
        if any(not isinstance(value, str) or not value for value in record.values()):
            raise ValueError("record values must be nonempty strings")
        if not re.fullmatch(r"[A-Z]{3}", record["currency"]):
            raise ValueError("invalid currency")
        if not re.fullmatch(r"\d+\.\d{2}", record["price"]):
            raise ValueError("price must retain two decimal places")
        if not record["href"].startswith("/") or record["href"].startswith("//"):
            raise ValueError("fixture link must be origin-relative")
    if len({record["sku"] for record in records}) != len(records):
        raise ValueError("duplicate SKU")
    if records != expected:
        raise ValueError("records do not match the independent literal oracle")
    return records


def summarize(documents):
    import json
    from expectations import expected_cases, expected_diagnostics
    if not isinstance(documents, list) or len(documents) != 2:
        raise ValueError("exactly two browser captures required")
    browsers = set()
    environments = []
    shared_runtime = None
    for document in documents:
        if set(document) != {"schema", "environment", "observations", "diagnostics"} or type(document["schema"]) is not int or document["schema"] != 1:
            raise ValueError("invalid capture schema")
        environment = document["environment"]
        if set(environment) != {"browser", "browser_version", "python", "playwright", "os", "architecture"}:
            raise ValueError("invalid environment fields")
        if any(not isinstance(v, str) or not v for v in environment.values()):
            raise ValueError("missing environment value")
        if environment["playwright"] != "1.63.0" or not environment["python"].startswith("3.12."):
            raise ValueError("unexpected dependency/runtime version")
        browser = environment["browser"]
        if browser not in {"chromium", "firefox"} or browser in browsers:
            raise ValueError("unexpected or duplicate browser")
        browsers.add(browser)
        environments.append(environment)
        runtime = {key: environment[key] for key in ("python", "playwright", "os", "architecture")}
        if shared_runtime is not None and runtime != shared_runtime:
            raise ValueError("browser captures must share runtime and OS")
        shared_runtime = runtime
        for key, expected in (("observations", expected_cases()), ("diagnostics", expected_diagnostics())):
            rows = document[key]
            wanted = {(round_id, case) for round_id in (1, 2, 3) for case in expected}
            found = set()
            if not isinstance(rows, list):
                raise ValueError("rows must be a list")
            for row in rows:
                if set(row) != {"round", "case", "observation"} or type(row["round"]) is not int:
                    raise ValueError("invalid row schema")
                identity = (row["round"], row["case"])
                if identity not in wanted or identity in found:
                    raise ValueError("unexpected or duplicate case/round")
                found.add(identity)
                observation = row["observation"]
                if json.dumps(observation, sort_keys=True) != json.dumps(expected[row["case"]], sort_keys=True):
                    raise ValueError(f"unexpected observation: {browser}/{row['round']}/{row['case']}")
                if "records" in observation:
                    validate_records(observation["records"], expected[row["case"]]["records"])
            if found != wanted:
                raise ValueError("incomplete case/round matrix")
    return {"schema": 1, "environments": environments, "browsers": 2, "rounds_per_browser": 3,
            "extraction_cases": len(CASE_IDS), "extraction_observations": 72,
            "diagnostic_cases": len(DIAGNOSTIC_IDS), "diagnostic_observations": 24,
            "passed": 96, "failed": 0}
