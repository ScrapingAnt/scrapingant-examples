"""Deterministic SVG calculation diagrams; source-dated rules and synthetic outputs."""
import argparse
from decimal import Decimal
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def svg(width, height, title, description, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<style>text{{font-family:Arial,sans-serif;fill:#142c43}}.heading{{font-weight:700}}.muted{{fill:#486477}}.small{{font-size:20px}}</style>
<rect width="{width}" height="{height}" fill="#f4f8fb"/>{body}</svg>\n'''


def text(x, y, value, size=24, cls=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" class="{cls}">{escape(value)}</text>'


def render():
    s1 = json.loads((ROOT / "expected_output/s1-event-included.json").read_text())
    s2 = json.loads((ROOT / "expected_output/s2-event-plus-usage.json").read_text())
    # Diagrams use recorded modeled amounts; they never invent consumption.
    body = text(32, 50, "Reconcile a monthly Apify bill", 29, "heading")
    body += text(32, 82, "Model scope: USD, known cycle totals", 21, "muted")
    nodes = [
        ("1  Confirm Actor prices and charged events", "Record Actor/build, source date and event divisor."),
        ("2  Determine Actor-run usage inclusion", "Included → add $0. Extra / usage-only → add meters."),
        ("3  Add post-run storage and transfer", "Separate scope; billable in every charging model."),
        ("4  Include other eligible account usage", "Exclude these Actor scopes from that other total."),
        ("5  Apply the account allowance once", "Paid overage = max(eligible usage − allowance, 0)."),
        ("6  Check missing inputs and Free feasibility", "Missing → partial. Above Free allowance → infeasible."),
        ("7  Attribute cycle cash cost", "Paid plan fee + overage + known extra cash charges."),
    ]
    for i, (heading, detail) in enumerate(nodes):
        y = 116 + i * 126
        body += f'<rect x="22" y="{y}" width="656" height="94" rx="12" fill="white" stroke="#bfd0dc"/>'
        body += text(40, y + 35, heading, 23, "heading") + text(40, y + 67, detail, 20)
        if i < len(nodes) - 1:
            body += f'<path d="M350 {y+98}v20m-6-6 6 6 6-6" fill="none" stroke="#168c82" stroke-width="3"/>'
    body += text(32, 1036, "Overage is added to the next invoice.", 22, "heading")
    body += text(32, 1070, "Rules checked 2026-10-02. Not an observed invoice.", 20, "muted")
    flow = svg(700, 1100, "Apify monthly charge reconciliation flow",
               "Identify event prices and run-usage inclusion; add post-run and other eligible usage; apply one allowance. Missing inputs prevent a precise bill. Free excess is infeasible. Paid cycle cost is plan fee plus next-invoice overage and known extra cash charges.", body)

    body = text(32, 48, "The monthly floor survives underuse", 29, "heading")
    body += text(32, 80, "SYNTHETIC Starter examples • not customer bills", 21, "muted")
    colors = ("#35566f", "#168c82")
    for i, data in enumerate((s1, s2)):
        y = 114 + i * 250
        body += f'<rect x="22" y="{y}" width="716" height="232" rx="12" fill="white" stroke="#bfd0dc"/>'
        title = "S1  Event price includes run usage" if i == 0 else "S2  Events plus run usage"
        body += text(40, y + 34, title, 25, "heading")
        body += text(40, y + 65, f"Eligible charges: ${data['known_workload_usage_usd']}", 22)
        fee = Decimal(data["monthly_plan_fee_usd"])
        overage = Decimal(data["overage_next_invoice_usd"])
        fee_width = fee * Decimal("24")
        extra_width = overage * Decimal("24")
        body += f'<rect x="40" y="{y+89}" width="{fee_width}" height="46" fill="{colors[0]}"/>'
        if extra_width:
            body += f'<rect x="{40+fee_width}" y="{y+89}" width="{extra_width}" height="46" fill="{colors[1]}"/>'
        body += text(40, y + 171, f"Cycle cash cost: ${data['cycle_cash_cost_usd']}", 25, "heading")
        body += text(40, y + 204, (f"Unused prepaid: ${data['unused_prepaid_usd']}" if i == 0 else
                                 f"Next-invoice overage: ${data['overage_next_invoice_usd']}"), 22)
    body += '<rect x="32" y="640" width="20" height="20" fill="#35566f"/>'
    body += text(64, 658, "Monthly plan fee ($19)", 21)
    body += '<rect x="388" y="640" width="20" height="20" fill="#168c82"/>'
    body += text(420, 658, "Overage beyond prepaid", 21)
    body += text(32, 700, "Synthetic quantity inputs; prices checked 2026-10-02.", 20, "muted")
    costs = svg(760, 730, "Synthetic Apify Starter bill calculation",
                "S1 includes run usage: eligible charges 0.632 dollars, modeled cycle bill 19 dollars, unused prepaid 18.368. S2 adds run usage: charges and cycle bill 22.272 dollars, next-invoice overage 3.272. Both are synthetic arithmetic examples.", body)

    body = '<rect width="1200" height="630" fill="#102a43"/>'
    body += '<style>text{fill:#fff}</style>'
    body += text(68, 80, "SCRAPINGANT · PRICING WORKSHEET", 24)
    body += text(68, 177, "Apify pricing", 66, "heading")
    body += text(68, 237, "Reconcile Actor charges and platform usage", 31)
    labels = [(68, "Events", "Charged counts × dated prices"),
              (429, "Extra usage", "Only when not included"),
              (790, "Post-run", "Storage and transfer")]
    for x, heading, detail in labels:
        body += f'<rect x="{x}" y="291" width="330" height="115" rx="12" fill="#244760"/>'
        body += text(x+22, 333, heading, 30, "heading") + text(x+22, 372, detail, 21)
    body += text(68, 476, "Apply one account allowance. Keep unknown inputs visible.", 29)
    body += text(68, 554, "Source-dated rules · Synthetic examples · Offline calculation", 24)
    banner = svg(1200, 630, "Apify Pricing: Reconcile Actor Charges and Platform Usage",
                 "Editorial calculation banner: events, extra usage and post-run costs feed one account allowance. Source-dated rules and synthetic examples, not an observed invoice.", body)
    return {"bill-flow.svg": flow, "synthetic-costs.svg": costs, "banner.svg": banner}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for filename, value in render().items():
        path = ROOT / "visuals" / filename
        if args.check:
            if not path.exists() or path.read_bytes() != value.encode():
                raise SystemExit("SVG mismatch: " + filename)
        else:
            path.write_bytes(value.encode())
    print("Verified 3 rule/calculation SVGs." if args.check else "Rendered 3 rule/calculation SVGs.")


if __name__ == "__main__":
    main()
