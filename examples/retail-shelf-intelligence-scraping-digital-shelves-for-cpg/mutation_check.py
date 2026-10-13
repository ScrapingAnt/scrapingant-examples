"""Prove selected tests fail for real extraction/retention/transport mutations."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).parent
SOURCE = (ROOT / "collector.py").read_text()
controls = [
    ("wrong selected price", '"price":price, "currency":"USD"', '"price":"2.00", "currency":"USD"',
     "test_collector.Records.test_selected_offers_match_independent_literal_oracle"),
    ("wrong pack unit", '"pack_unit":"ounce"', '"pack_unit":"gram"',
     "test_collector.Records.test_selected_offers_match_independent_literal_oracle"),
    ("OOS collapsed to unknown", '"https://schema.org/OutOfStock":"out_of_stock"', '"https://schema.org/OutOfStock":"unknown"',
     "test_collector.Records.test_explicit_OOS_and_unknown_remain_distinct"),
    ("partial prior record dropped", 'report["unobserved_prior_records"].append(old)', 'pass  # MUTANT: prior record lost',
     "test_changes.Changes.test_partial_omission_retains_prior_record_and_original_time"),
    ("unknown credits become zero", '"actual_receipt_credits":None, "credit_receipt_state":"unknown" if managed', '"actual_receipt_credits":0, "credit_receipt_state":"unknown" if managed',
     "test_transport.Managed.test_unknown_and_malformed_credit_cost_remain_unknown"),
    ("key leaked into URL", 'request = Request(request_url, headers=', 'request_url += "&api_key=" + key if managed else ""\n    request = Request(request_url, headers=',
     "test_transport.Managed.test_explicit_header_auth_and_request_settings"),
]
for name, old, new, test in controls:
    if SOURCE.count(old) != 1:
        raise RuntimeError("mutation_anchor_changed: " + name)
    with tempfile.TemporaryDirectory(prefix="retail-negative-") as directory:
        target = Path(directory)
        shutil.copytree(ROOT / "fixtures", target / "fixtures")
        for filename in ("test_collector.py","test_changes.py","test_transport.py"):
            shutil.copyfile(ROOT / filename,target / filename)
        (target / "collector.py").write_text(SOURCE.replace(old,new,1))
        process = subprocess.run([sys.executable,"-m","unittest",test],cwd=target,text=True,capture_output=True,timeout=20)
        # Syntax/import errors do not establish that a behavioral assertion caught it.
        if process.returncode == 0 or "FAIL:" not in process.stderr or "ERROR:" in process.stderr:
            raise RuntimeError("negative_control_not_caught: " + name)
        print(f"Caught: {name}; {test}; exit={process.returncode}")
print(f"Behavior mutations caught: {len(controls)}/{len(controls)}")
