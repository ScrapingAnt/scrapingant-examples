"""Capture real offline CLI output and compare it with independent literal fields."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import collector

ROOT = Path(__file__).parent
OUT = ROOT / "expected_output"
OUT.mkdir(exist_ok=True)

def capture(name, command, exit_code):
    process = subprocess.run([sys.executable,"collector.py",*command], cwd=ROOT, text=True, capture_output=True)
    if process.returncode != exit_code or process.stderr:
        raise RuntimeError("unexpected_CLI_result")
    (OUT / f"{name}.json").write_text(process.stdout)
    return json.loads(process.stdout)

def write_json(name, value):
    (OUT / f"{name}.json").write_text(json.dumps(value,indent=2,sort_keys=True) + "\n")

def csv_records(name, records):
    with (OUT / name).open("w",newline="") as output:
        writer = csv.DictWriter(output,fieldnames=list(records[0]),lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({key:json.dumps(value,sort_keys=True) if isinstance(value,dict) else value for key,value in record.items()})

before = capture("baseline",["replay","fixtures/baseline.html","--observed-at","2026-10-13T11:00:00Z"],0)
after = capture("changed",["replay","fixtures/changed.html","--observed-at","2026-10-13T12:00:00Z"],0)
partial = capture("partial",["replay","fixtures/partial.html","--observed-at","2026-10-13T12:00:00Z"],1)
changed_pack = capture("changed-pack",["replay","fixtures/changed-pack.html","--observed-at","2026-10-13T12:00:00Z"],1)
for name,result in (("baseline",before),("changed",after),("partial",partial)):
    collector.verify_oracle(result["records"],json.loads((ROOT / f"fixtures/{name}-records.json").read_text()))
changes = collector.change_report(before,after)
partial_changes = collector.change_report(before,partial)
pack_changes = collector.change_report(before,changed_pack)
write_json("changes",changes)
write_json("partial-changes",partial_changes)
write_json("changed-pack-changes",pack_changes)
csv_records("records.csv",before["records"])
source = capture("adagio-projection-replay",["projection","fixtures/adagio-field-projection.json"],0)
managed_observation = json.loads((OUT / "managed-2026-10-13/collection.json").read_text())
projected_fields = [{"product_group_id":r["product_id"],"sku":r["sku"],"size_literal":r["variant"],
    "pack_size":r["pack_quantity"],"pack_unit":{"ounce":"oz"}[r["pack_unit"]],"pack_measure":"weight",
    "price_decimal":r["price"],"currency":r["currency"],"availability_literal":r["source_evidence"]["availability_token"],
    "market":r["market"],"market_basis":"page microdata shippingDestination.addressCountry=US" if r["market_basis"] == "page_shipping_destination" else "unknown",
    "offer_basis":r["offer_kind"],"purchase_basis":r["purchase_basis"],"fulfilment":r["fulfilment"]} for r in source["records"]]
collector.verify_oracle(projected_fields,json.loads((ROOT / "fixtures/adagio-source-oracle.json").read_text()))
csv_records("adagio-projection-records.csv",source["records"])
group = json.loads((ROOT / "fixtures/baseline.html").read_text().split('<script type="application/ld+json">')[1].split('</script>')[0])
write_json("naive-price",{"naive_group_low_price":group["offers"]["lowPrice"],
    "selected_SKU":before["records"][0]["sku"],"selected_pack":before["records"][0]["variant"],
    "selected_offer_price":before["records"][0]["price"],"currency":"USD","matches":False,
    "scope":"owned fictional data; aggregate sample price cannot be assigned to the selected weight offer"})
summary = [
    f"Runtime: {sys.implementation.name} {sys.version.split()[0]}; standard library only",
    "Default scope: owned fixtures and saved factual projection; no external/provider/model calls",
    f"Owned baseline: {len(before['records'])}/2 selected offers accepted; complete={str(before['complete']).lower()}",
    f"Owned changed: {len(after['records'])}/2 selected offers accepted; comparable field changes={len(changes['changes'])}",
    f"Owned partial: {len(partial['records'])}/2 selected offers accepted; unobserved prior records={len(partial_changes['unobserved_prior_records'])}",
    f"Changed-pack control: {len(changed_pack['records'])}/2 accepted; reason={changed_pack['rejected'][0]['reason']}; prior pack retained={len(pack_changes['unobserved_prior_records'])}",
    "Missing observations make no out-of-stock or disappearance claim; prior timestamps retained",
    f"Naive from/sample price={group['offers']['lowPrice']}; selected 3oz offer={before['records'][0]['price']} USD",
    f"Adagio saved projection: {len(source['records'])}/2 literal offers match independent source oracle; no fresh HTTP request",
    f"Recorded managed observation: {managed_observation['acquisition']['requests']} request; API/target={managed_observation['acquisition']['api_http_status']}/{managed_observation['acquisition']['target_http_status']}; {managed_observation['cost']['accepted_records']}/2 accepted; receipt credits={managed_observation['cost']['actual_receipt_credits']}; credits per accepted record={managed_observation['cost']['credits_per_accepted_record']}",
    "Recorded managed data are read locally; standalone managed CLI excluded and no paid observation rerun",
]
print("\n".join(summary))
