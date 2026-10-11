#!/usr/bin/env python3
"""Explicit bounded live phase. Default run.sh never imports credentials or calls this."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import time

ENDPOINT = "https://api.scrapingant.com/mcp/"
SOURCE_URL = "https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html"
PROTOCOL = "2025-11-25"
TOOLS = {arm: "get_web_page_" + arm for arm in ("html", "markdown", "text")}
MAX_ATTEMPTS = 15

class StopRun(RuntimeError): pass

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()

def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(data, stream, indent=2); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)

def call_plan():
    rng = random.Random(8)
    result = []
    for repeat in range(5):
        arms = list(TOOLS); rng.shuffle(arms)
        result.extend((arm, repeat) for arm in arms)
    return result

def decode_rpc(raw, content_type):
    if content_type.startswith("text/event-stream"):
        messages = []
        for event in raw.replace("\r\n", "\n").split("\n\n"):
            lines = [line[5:].lstrip() for line in event.splitlines() if line.startswith("data:")]
            if lines: messages.append(json.loads("\n".join(lines)))
        return messages[-1] if messages else None
    return json.loads(raw) if raw.strip() else None

def check_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("read_only_verified") is not True or snapshot.get("physical_standby") is not False or snapshot.get("matching_tokens") != 1 or snapshot.get("active_periods") != 1:
        raise StopRun("usage_scope_unverified")
    for key in ("used_credits", "total_credits"):
        if type(snapshot.get(key)) is not int or snapshot[key] < 0: raise StopRun("usage_counter_invalid")
    if not snapshot.get("period_ref"): raise StopRun("usage_period_unverified")
    return snapshot

class LiveRun:
    def __init__(self, out, transport, secret, required_values, usage=None, expected_html_sha256=None):
        self.out = Path(out); self.out.mkdir(parents=True, exist_ok=False)
        self.transport, self.secret = transport, secret
        self.required_values, self.usage = required_values, usage
        self.expected_html_sha256 = expected_html_sha256
        self.stopped = False
        self.ledger = {"started_at_utc": now(), "client": {"name":"issue8-bounded-mcp", "version":"1.0"},
                       "source_url":SOURCE_URL, "maximum_attempts":MAX_ATTEMPTS, "credit_ceiling":15,
                       "documented_credit_bound_per_attempt":1, "reserved_credit_upper_bound":0,
                       "retry_policy":"none; unknown attempts remain reserved", "calls":[], "model_calls":0,
                       "plan":call_plan(), "plan_seed":8, "exact_llm_accuracy":None,
                       "actual_tool_credit_receipts":None, "cost_per_model_correct_output":None,
                       "account_delta_caveat":"Contemporaneous account deltas are not exclusive request receipts; concurrent usage cannot be ruled out."}
        self.previous = None
        if usage:
            try: self.previous = check_snapshot(usage())
            except Exception:
                self.ledger["stop_reason"] = "usage_preflight_failed"; self.save(); raise StopRun("usage_preflight_failed") from None
            if self.previous["total_credits"] - self.previous["used_credits"] < 15:
                self.ledger["stop_reason"] = "insufficient_remaining_credits"; self.save(); raise StopRun("insufficient_remaining_credits")
            self.ledger["initial_usage"] = self.previous
        self.save()

    def save(self): atomic_json(self.out / "ledger.json", self.ledger)

    def stop(self, reason):
        self.stopped = True; self.ledger["stop_reason"] = reason; self.save(); raise StopRun(reason) from None

    def observe(self, arm, repeat):
        if self.stopped: raise StopRun("already_stopped")
        if len(self.ledger["calls"]) >= MAX_ATTEMPTS: self.stop("approved_cap_exhausted")
        if arm not in TOOLS: self.stop("unsupported_arm")
        number = len(self.ledger["calls"]) + 1
        request = {"jsonrpc":"2.0", "id":number + 9, "method":"tools/call", "params":{
            "name":TOOLS[arm], "arguments":{"url":SOURCE_URL, "browser":False, "proxy_type":"datacenter", "proxy_country":"US"}}}
        row = {"attempt":number, "arm":arm, "repeat":repeat, "request":request,
               "request_sha256":digest(json.dumps(request,sort_keys=True).encode()), "started_at_utc":now(),
               "reserved_credits":1, "outcome":"reserved_before_transport", "observed_account_delta":None}
        self.ledger["calls"].append(row); self.ledger["reserved_credit_upper_bound"] += 1; self.save()
        started = time.perf_counter()
        try: response = self.transport(request)
        except BaseException as exc:
            row.update(ended_at_utc=now(), elapsed_ms=(time.perf_counter()-started)*1000,
                       outcome="transport_unknown", error_type=type(exc).__name__)
            self.stop("transport_outcome_unknown")
        row.update(ended_at_utc=now(), elapsed_ms=(time.perf_counter()-started)*1000, http_status=response.status_code)
        raw = response.text
        headers = {k:v for k,v in response.headers.items() if k.lower() not in {"set-cookie","authorization","x-api-key","mcp-session-id"}}
        echo = bool(self.secret) and (self.secret in raw or self.secret in json.dumps(headers))
        if echo:
            raw = raw.replace(self.secret, "[REDACTED_CREDENTIAL]")
            headers = {k:v.replace(self.secret,"[REDACTED_CREDENTIAL]") for k,v in headers.items()}
        response_path = self.out / f"response-{number:03d}.txt"
        response_path.write_text(raw)
        row.update(response_file=response_path.name, response_sha256=digest(raw.encode()), response_headers=headers, credential_echo=echo)
        if echo:
            row["outcome"] = "credential_echo_stopped"; self.stop("credential_echo")
        if response.status_code != 200:
            row["outcome"] = "http_error"
        else:
            try:
                rpc = decode_rpc(raw, response.headers.get("content-type", ""))
                if not isinstance(rpc, dict): raise ValueError()
                if rpc.get("jsonrpc") != "2.0" or rpc.get("id") != request["id"]: row["outcome"] = "rpc_id_mismatch"
                elif "error" in rpc: row["outcome"] = "rpc_error"
                else:
                    result = rpc["result"]
                    if not isinstance(result,dict): raise ValueError()
                    blocks = result.get("content", [])
                    if not isinstance(blocks,list) or any(not isinstance(block,dict) or not isinstance(block.get("type"),str) or (block["type"]=="text" and not isinstance(block.get("text"),str)) for block in blocks): raise ValueError()
                    if result.get("isError") is not None and type(result["isError"]) is not bool: raise ValueError()
                    content = "\n".join(block["text"] for block in blocks if block.get("type")=="text")
                    content_path = self.out / f"content-{number:03d}.{ {'html':'html','markdown':'md','text':'txt'}[arm]}"
                    content_path.write_text(content)
                    row.update(content_file=content_path.name, content_sha256=digest(content.encode()),
                               content_bytes=len(content.encode()), tool_is_error=result.get("isError"),
                               text_blocks=sum(block.get("type")=="text" for block in blocks),
                               required_values_survive=all(value in content for value in self.required_values))
                    row["outcome"] = "tool_error" if result.get("isError") else ("required_values_present" if row["required_values_survive"] else "required_values_missing")
                    if arm == "html": row["matches_frozen_html"] = row["content_sha256"] == self.expected_html_sha256
            except (ValueError, KeyError, TypeError): row["outcome"] = "malformed_rpc"
        self.save()
        if self.usage:
            try:
                after = check_snapshot(self.usage()); row["usage_after"] = after
                if after["period_ref"] != self.previous["period_ref"] or after["total_credits"] != self.previous["total_credits"]:
                    self.stop("usage_period_changed")
                delta = after["used_credits"] - self.previous["used_credits"]
                row["observed_account_delta"] = delta
                if delta not in (0,1): self.stop("usage_anomaly")
                self.previous = after
            except StopRun:
                if not self.stopped: self.stop("usage_snapshot_scope_failed")
                raise
            except Exception: self.stop("usage_snapshot_failed")
        self.save()
        if row["outcome"] in ("rpc_id_mismatch","malformed_rpc"): self.stop(row["outcome"])
        return row

def execute(out, key, usage=None):
    """Only call after a fresh bounded approval. No automatic retry or account lookup."""
    import requests
    root = Path(__file__).resolve().parent
    oracle = json.loads((root / "ground_truth.json").read_text())
    # Frozen twelve catalog field slots, kept separate from content generation.
    records = oracle["catalog"] if "catalog" in oracle else oracle["cases"]["catalog"]["records"]
    required = [v for record in records for v in record.values() if v is not None]
    session = requests.Session(); session.trust_env = False
    headers = {"Content-Type":"application/json", "Accept":"application/json, text/event-stream", "x-api-key":key}
    def transport(payload):
        return session.post(ENDPOINT, headers=headers, json=payload, timeout=(10,60), allow_redirects=False)
    run = LiveRun(out,transport,key,required,usage=usage,expected_html_sha256=digest((root/"fixtures/catalog.html").read_bytes()))
    run.ledger["runtime"] = {"requests":requests.__version__, "python":__import__('platform').python_version()}
    discovery = []
    try:
        for payload in [{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":PROTOCOL,"capabilities":{},"clientInfo":run.ledger["client"]}}, {"jsonrpc":"2.0","method":"notifications/initialized"}, {"jsonrpc":"2.0","id":2,"method":"tools/list"}]:
            response = transport(payload)
            if key in response.text: run.stop("credential_echo_discovery")
            discovery.append({"request":payload,"status":response.status_code,"content_type":response.headers.get("content-type"),"raw_response":response.text})
            if response.status_code not in (200,202): run.stop("discovery_http_error")
            decoded = decode_rpc(response.text,response.headers.get("content-type",""))
            if "id" in payload and (not isinstance(decoded,dict) or decoded.get("jsonrpc")!="2.0" or decoded.get("id")!=payload["id"] or "error" in decoded):
                run.stop("discovery_rpc_identity")
            if payload["method"] == "initialize":
                result=decoded["result"]
                if result["protocolVersion"] != PROTOCOL: run.stop("protocol_drift")
                run.ledger["negotiated_protocol"] = result["protocolVersion"]; run.ledger["server_info"] = result["serverInfo"]
                headers["MCP-Protocol-Version"] = result["protocolVersion"]
            if payload["method"] == "tools/list":
                tools=decoded["result"]["tools"]
                expected=json.loads((root/"expected_output/public-discovery.json").read_text())["tools"]
                if {t["name"]:t["inputSchema"] for t in tools} != {t["name"]:t["inputSchema"] for t in expected}: run.stop("tool_schema_drift")
                run.ledger["tools"] = tools
        atomic_json(run.out/"discovery.json",discovery); run.save()
        for arm,repeat in call_plan():
            row=run.observe(arm,repeat)
            print(json.dumps({k:row.get(k) for k in ("attempt","arm","repeat","outcome","content_bytes","observed_account_delta")} ),flush=True)
        run.ledger["completed_at_utc"] = now(); run.ledger["complete"] = True; run.save()
    except StopRun: raise
    except BaseException as exc:
        run.ledger["preflight_error_type"] = type(exc).__name__; run.stop("discovery_unknown")
    finally:
        atomic_json(run.out/"discovery.json",discovery); session.close()
    return run.ledger

if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute-approved-15-call-run",action="store_true",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    key=os.environ.get("SCRAPINGANT_API_KEY")
    if not key: raise SystemExit("SCRAPINGANT_API_KEY is required; do not paste credentials into commands")
    try: execute(args.out,key)
    except StopRun as exc: raise SystemExit(str(exc)) from None
