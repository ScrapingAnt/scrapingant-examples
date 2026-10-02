"""Capture or check deterministic offline synthetic JSON/CSV worksheets."""
import argparse
import csv
import io
import json

from model import PACKET, reconcile, unique_object


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare existing output bytes without writing")
    args = parser.parse_args()
    rates = json.loads((PACKET / "rates.json").read_text(), object_pairs_hook=unique_object)
    summaries, outputs = [], {}
    summary_fields = ["label", "input_type", "status", "known_workload_usage_usd", "known_account_usage_usd",
                      "prepaid_applied_usd", "unused_prepaid_usd", "overage_next_invoice_usd",
                      "cycle_cash_cost_usd", "known_cash_lower_bound_usd", "incremental_workload_cash_usd",
                      "accepted_output_count", "workload_usage_per_accepted_output_usd"]
    for fixture in sorted((PACKET / "fixtures").glob("s*.json")):
        result = reconcile(json.loads(fixture.read_text(), object_pairs_hook=unique_object), rates)
        outputs[fixture.stem + ".json"] = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=list(result["lines"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["lines"])
        outputs[fixture.stem + ".csv"] = buf.getvalue()
        summaries.append({field: result[field] for field in summary_fields})
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=summary_fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(summaries)
    outputs["scenario-summary.csv"] = buf.getvalue()
    mismatches = []
    for name, output in outputs.items():
        path = PACKET / "expected_output" / name
        if args.check:
            if not path.exists() or path.read_bytes() != output.encode("utf-8"):
                mismatches.append(name)
        else:
            path.write_bytes(output.encode("utf-8"))
    if mismatches:
        print("Saved output mismatch: " + ", ".join(mismatches))
        return 1
    print(f"{'Verified' if args.check else 'Captured'} {len(summaries)} synthetic scenarios / {len(outputs)} output files offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
