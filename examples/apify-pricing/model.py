"""Offline, source-dated arithmetic. Does not call Apify or estimate consumption."""
import argparse
import calendar
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

PACKET = Path(__file__).resolve().parent
ZERO = Decimal("0")


def number(value, field, *, integer=False, positive=False):
    """Null is unknown; floats/bools and invalid quantities cannot be monetary input."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field}: use a decimal string or integer, never float/bool")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(f"{field}: must be finite and {'positive' if positive else 'nonnegative'}")
    if abs(result.adjusted()) > 24 or len(result.as_tuple().digits) > 28:
        raise ValueError(f"{field}: exceeds worksheet numeric precision range")
    if integer and result != result.to_integral_value():
        raise ValueError(f"{field}: must be an integer count")
    return result


def decimal_text(value):
    if value is None:
        return None
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def known_source(value, field):
    if value is None:
        return False
    if not isinstance(value, dict):
        raise ValueError(f"{field}: requires dated official public source metadata")
    if not value.get("url") or not value.get("checked_on"):
        return False
    u = urlsplit(value["url"])
    if (u.scheme != "https" or u.hostname not in
            {"apify.com", "docs.apify.com", "help.apify.com"} or
            u.query or u.username or u.password):
        raise ValueError(f"{field}: requires an official public URL without credentials/query")
    try:
        date.fromisoformat(value["checked_on"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: invalid checked_on date") from exc
    return True


def allowed_keys(value, names, field):
    if not isinstance(value, dict) or set(value) - set(names):
        raise ValueError(f"{field}: unknown keys or invalid object")


def reconcile(manifest, rates):
    # High fixed precision for subcent rates; never round each line to cents.
    with localcontext() as ctx:
        ctx.prec = 60
        return _reconcile(manifest, rates)


def _reconcile(m, rates):
    if rates.get("schema_version") != 1 or not known_source(
            {"url": rates.get("source_url"), "checked_on": rates.get("checked_on")},
            "rate snapshot"):
        raise ValueError("rate snapshot requires schema_version=1 and dated official provenance")
    allowed_keys(m, ("schema_version", "label", "input_type", "currency", "cadence",
                    "period_start", "period_end", "plan", "other_account_usage_usd",
                    "extra_cash_charges_usd", "unresolved_items", "actors", "accepted_outputs"),
                 "manifest")
    if m.get("schema_version") != 1 or not m.get("label"):
        raise ValueError("requires schema_version=1 and a named input label")
    if m.get("input_type") not in ("synthetic", "user_supplied"):
        raise ValueError("requires explicit synthetic or user_supplied input_type")
    if m.get("currency") != "USD" or rates.get("currency") != "USD":
        raise ValueError("only USD is supported; no currency conversion")
    if m.get("cadence") != "monthly" or rates.get("cadence") != "monthly":
        raise ValueError("only full monthly cycles are supported; annual/prorated plans unresolved")
    try:
        start = date.fromisoformat(m["period_start"])
        end = date.fromisoformat(m["period_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("requires ISO dates for a complete billing cycle") from exc
    year, month = start.year + (start.month == 12), start.month % 12 + 1
    next_cycle = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
    if end != next_cycle:
        raise ValueError("period_end must be one calendar month after start (exclusive)")
    if m.get("plan") not in rates["plans"]:
        raise ValueError("requires a verified monthly plan; custom plans are unresolved")
    plan = rates["plans"][m["plan"]]
    if not isinstance(plan.get("overage_available"), bool):
        raise ValueError("plan overage_available must be a boolean")
    fee = number(plan["monthly_fee_usd"], "plan fee")
    prepaid = number(plan["prepaid_usage_usd"], "prepaid")
    unresolved, memo_unknown, rows = [], [], []
    workload_unknown = []
    known_workload = ZERO

    def gap(text, *, workload=True, memo=False):
        if memo:
            memo_unknown.append(text)
        else:
            unresolved.append(text)
            if workload:
                workload_unknown.append(text)

    actors = m.get("actors")
    if not isinstance(actors, list):
        raise ValueError("actors must be a list of nonoverlapping Actor/version scopes")
    actor_ids = set()
    for a in actors:
        allowed_keys(a, ("id", "version", "price_source", "pricing_model", "events",
                         "run_usage", "post_run_usage"), "actor")
        aid = a.get("id")
        if not isinstance(aid, str) or not aid or aid in actor_ids:
            raise ValueError("Actor IDs must be nonempty and unique; aggregate each scope once")
        actor_ids.add(aid)
        if not a.get("version"):
            gap(f"{aid}: Actor version missing")
        if not known_source(a.get("price_source"), f"{aid} pricing source"):
            gap(f"{aid}: dated Actor pricing source missing")
        model = a.get("pricing_model")
        if model not in (None, "event_included", "event_plus_usage", "usage_only"):
            raise ValueError(f"{aid}: unsupported model (rental migration must be verified)")
        if model is None:
            gap(f"{aid}: charging model/inclusion unknown")
        events = a.get("events")
        if events is None:
            gap(f"{aid}: full charged-event list missing")
            events = []
        if not isinstance(events, list) or (model == "usage_only" and events):
            raise ValueError(f"{aid}: usage-only cannot carry developer event charges")
        event_names = set()
        for event in events:
            allowed_keys(event, ("name", "charged_count", "unit", "unit_price_usd", "price_per",
                                 "currency", "source"), f"{aid} event")
            name = event.get("name")
            if not isinstance(name, str) or not name or name in event_names:
                raise ValueError(f"{aid}: duplicate or unnamed event")
            event_names.add(name)
            if event.get("unit") != "event" or event.get("currency") != "USD":
                raise ValueError(f"{aid}/{name}: requires event units and USD")
            count = number(event.get("charged_count"), name, integer=True)
            price = number(event.get("unit_price_usd"), name + " price")
            per = number(event.get("price_per"), name + " divisor", positive=True, integer=True)
            source_ok = known_source(event.get("source"), name + " source")
            amount = count * price / per if None not in (count, price, per) and source_ok else None
            if amount is None or model is None:
                gap(f"{aid}/event/{name}: charged count, price, source or inclusion unknown")
                billable = None
            else:
                billable = amount
                known_workload += billable
            rows.append({"actor": aid, "scope": "event", "item": name, "quantity": decimal_text(count),
                         "unit": "event", "price_usd": decimal_text(price), "price_per": decimal_text(per),
                         "rated_amount_usd": decimal_text(amount), "billed_amount_usd": decimal_text(billable),
                         "treatment": "billed" if billable is not None else "unknown",
                         "source": (event.get("source") or {}).get("url")})

        for scope in ("run_usage", "post_run_usage"):
            usage = a.get(scope)
            if usage is None:
                usage = {}
            names = [name for name in rates["meters"] if scope == "run_usage" or
                     name.startswith(("dataset_", "kv_", "queue_", "transfer_"))]
            allowed_keys(usage, names, f"{aid}/{scope}")
            included = scope == "run_usage" and model == "event_included"
            uncertain = scope == "run_usage" and model is None
            for name in names:
                spec = rates["meters"][name]
                meter = usage.get(name)
                quantity = None
                if meter is not None:
                    allowed_keys(meter, ("quantity", "unit"), f"{aid}/{scope}/{name}")
                    if meter.get("unit") != spec["unit"]:
                        raise ValueError(f"{aid}/{scope}/{name}: unit must be {spec['unit']}")
                    quantity = number(meter.get("quantity"), name,
                                      integer=spec["unit"] in ("SERP", "operation", "request"))
                price = number(spec["prices_usd"][m["plan"]], name + " rate")
                per = number(spec["price_per"], name + " divisor", positive=True)
                amount = quantity * price / per if quantity is not None else None
                if quantity is None:
                    gap(f"{aid}/{scope}/{name}: measured or explicit synthetic quantity missing", memo=included)
                billable = ZERO if included else None if uncertain else amount
                if billable is not None:
                    known_workload += billable
                rows.append({"actor": aid, "scope": scope, "item": name,
                             "quantity": decimal_text(quantity), "unit": spec["unit"],
                             "price_usd": decimal_text(price), "price_per": decimal_text(per),
                             "rated_amount_usd": decimal_text(amount), "billed_amount_usd": decimal_text(billable),
                             "treatment": "included_in_event_price" if included else
                             "unknown" if billable is None else "billed",
                             "source": rates["source_url"]})

    other = number(m.get("other_account_usage_usd"), "other_account_usage_usd")
    extra_cash = number(m.get("extra_cash_charges_usd"), "extra_cash_charges_usd")
    if other is None:
        gap("Other account prepaid-eligible usage unknown", workload=False)
    if extra_cash is None:
        gap("Additional cash charges outside prepaid usage unknown", workload=False)
    if m.get("unresolved_items") is None:
        gap("Completeness attestation unresolved_items missing", workload=False)
    elif not isinstance(m["unresolved_items"], list) or any(
            not isinstance(x, str) or not x.strip() for x in m["unresolved_items"]):
        raise ValueError("unresolved_items must contain nonempty descriptions")
    else:
        for text in m["unresolved_items"]:
            gap(text)  # Conservative: an uncategorized gap may affect workload cost too.
    known_account = known_workload + (other if other is not None else ZERO)
    known_excess = max(ZERO, known_account - prepaid)
    free_exceeded = not plan["overage_available"] and known_account > prepaid
    complete = not unresolved and not free_exceeded
    applied = min(known_account, prepaid) if complete else None
    overage = known_excess if complete else None
    cycle_cash = fee + overage + extra_cash if complete else None
    incremental = (max(ZERO, known_account - prepaid) - max(ZERO, other - prepaid)
                   if complete else None)
    lower_bound = None if free_exceeded else fee + known_excess + (extra_cash or ZERO)

    accepted = m.get("accepted_outputs")
    if accepted is None:
        accepted = {"count": None, "unit": "record", "definition": "unknown acceptance definition"}
    allowed_keys(accepted, ("count", "unit", "definition"), "accepted_outputs")
    if any(not isinstance(accepted.get(key), str) or not accepted[key].strip()
           for key in ("unit", "definition")):
        raise ValueError("accepted outputs require a named unit and validation definition")
    count = number(accepted.get("count"), "accepted outputs", integer=True)
    unit_reason = ("free allowance exceeded; workload not feasible on this plan" if free_exceeded else
                   "accepted output count unknown" if count is None else
                   "zero accepted outputs: unit cost is undefined" if count == 0 else
                   "workload billable inputs incomplete" if workload_unknown else None)
    return {
        "label": m["label"], "input_type": m["input_type"], "currency": "USD", "cadence": "monthly",
        "period_start": m["period_start"], "period_end_exclusive": m["period_end"],
        "price_snapshot_checked_on": rates["checked_on"],
        "status": "free_allowance_exceeded" if free_exceeded else "partial" if unresolved else "complete",
        "known_workload_usage_usd": decimal_text(known_workload),
        "known_account_usage_usd": decimal_text(known_account),
        "monthly_plan_fee_usd": decimal_text(fee), "prepaid_allowance_usd": decimal_text(prepaid),
        "prepaid_applied_usd": decimal_text(applied),
        "unused_prepaid_usd": decimal_text(prepaid - applied) if applied is not None else None,
        "overage_next_invoice_usd": decimal_text(overage),
        "cycle_cash_cost_usd": decimal_text(cycle_cash),
        "display_cycle_cash_cost_usd": format(cycle_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        if cycle_cash is not None else None,
        "known_cash_lower_bound_usd": decimal_text(lower_bound),
        "incremental_workload_cash_usd": decimal_text(incremental),
        "free_allowance_shortfall_usd": decimal_text(known_excess) if free_exceeded else None,
        "accepted_output_count": decimal_text(count), "accepted_output_unit": accepted["unit"],
        "acceptance_definition": accepted["definition"],
        "workload_usage_per_accepted_output_usd": decimal_text(known_workload / count)
        if not unit_reason else None,
        "account_cash_per_accepted_output_usd": decimal_text(cycle_cash / count)
        if cycle_cash is not None and count else None,
        "unit_cost_unresolved_reason": unit_reason,
        "unresolved": unresolved, "memo_unknown": memo_unknown, "lines": rows,
        "limitations": [
            "Arithmetic on supplied quantities; no provider execution, invoice observation or consumption prediction.",
            "Cycle cash cost attributes plan fee plus this cycle's overage; overage is invoiced next cycle.",
            "Current price snapshot is not the historical invoice rate; source metadata requires human verification.",
            "Display cents use one final ROUND_HALF_UP; Apify invoice rounding and adjustments are unverified.",
            "Other account usage must exclude these Actor scopes; extra cash must exclude prepaid-eligible charges.",
            "Counts are already charged events, not attempted/produced/accepted counts; no spend-cap simulation.",
            "GB and GB-hour quantities must use provider meters; no unverified bytes-to-GB conversion.",
            "Account bill per accepted output includes other usage/add-ons; it is not workload marginal cost.",
        ],
    }


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--rates", type=Path, default=PACKET / "rates.json")
    parser.add_argument("--csv", type=Path, help="Write line-item worksheet; blank is unknown, not zero")
    args = parser.parse_args()
    try:
        result = reconcile(json.loads(args.manifest.read_text(), object_pairs_hook=unique_object),
                           json.loads(args.rates.read_text(), object_pairs_hook=unique_object))
        if args.csv:
            fields = ["actor", "scope", "item", "quantity", "unit", "price_usd", "price_per",
                      "rated_amount_usd", "billed_amount_usd", "treatment", "source"]
            with args.csv.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(result["lines"])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Worksheet input error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
