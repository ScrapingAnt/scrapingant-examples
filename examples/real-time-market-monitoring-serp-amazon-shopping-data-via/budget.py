"""Documented datacenter-mode credit arithmetic, not measured invoices."""
import json


def workload(queries, marketplaces, pages, runs_per_day, days, attempts_per_page=1):
    values = (queries, marketplaces, pages, runs_per_day, days, attempts_per_page)
    if any(type(n) is not int or n < 1 for n in values):
        raise ValueError("positive integer workload dimensions required")
    snapshots = queries * marketplaces * runs_per_day * days
    initial_calls = snapshots * pages
    attempted_calls_cap = initial_calls * attempts_per_page
    return {"queries": queries, "marketplaces": marketplaces, "pages": pages,
            "runs_per_day": runs_per_day, "days": days, "attempts_per_page_cap": attempts_per_page,
            "snapshots": snapshots, "initial_calls": initial_calls, "attempted_calls_cap": attempted_calls_cap,
            "raw_datacenter_credits_at_cap": attempted_calls_cap,
            "rendered_datacenter_credits_at_cap": attempted_calls_cap * 10}


if __name__ == "__main__":
    print(json.dumps(workload(5, 1, 1, 24, 30, 2), indent=2, sort_keys=True))
