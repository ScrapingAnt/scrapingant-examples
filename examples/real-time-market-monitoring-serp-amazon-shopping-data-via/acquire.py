"""Optional one-page ScrapingAnt HTML capture. Not called by run.sh."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ENDPOINT = "https://api.scrapingant.com/v2/general"
MAX_BYTES = 2_000_000


class AcquisitionError(Exception):
    """Sanitized error: never include a target URL, token or upstream detail."""


def fetch_html(target, browser, max_attempts=1, max_credits=10, *, opener=urlopen, pause=time.sleep):
    source = urlsplit(target)
    if source.scheme != "https" or not source.hostname or source.username or source.password or source.fragment:
        raise AcquisitionError("Use one permitted public HTTPS target URL without credentials or fragment.")
    if type(browser) is not bool or max_attempts not in (1, 2):
        raise AcquisitionError("Explicit browser mode and one or two attempts are required.")
    per_attempt = 10 if browser else 1
    # Reserve one documented success cost per possible attempt. This is a local
    # planning cap, not a server billing limit; verify actual receipt headers.
    if max_credits < per_attempt * max_attempts:
        raise AcquisitionError("Insufficient credit reserve for the attempt cap.")
    token = os.environ.get("SCRAPINGANT_API_KEY", "")
    if not token.strip():
        raise AcquisitionError("Set SCRAPINGANT_API_KEY in your environment.")
    params = {"url": target, "browser": str(browser).lower(), "proxy_type": "datacenter",
              "proxy_country": "us", "timeout": "30", "return_page_source": "false"}
    request = Request(ENDPOINT + "?" + urlencode(params), headers={"x-api-key": token})
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=35) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise AcquisitionError("Response exceeds the local capture byte limit.")
                target_status = response.headers.get("Ant-page-status-code")
                # General responses expose target headers with this namespace;
                # an outer Content-Type is not guaranteed by the service.
                original_type = response.headers.get("Ant-original-header-content-type")
                content_type = (original_type if original_type is not None else response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                if response.status != 200 or target_status != "200" or content_type not in ("text/html", "application/xhtml+xml"):
                    raise AcquisitionError("HTML capture rejected by status or content type; no snapshot accepted.")
                receipt = response.headers.get("Ant-credits-cost")
                try:
                    cost = int(receipt)
                    if cost < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    raise AcquisitionError("Missing or invalid credit receipt; inspect locally before more calls.") from None
                if cost > max_credits:
                    raise AcquisitionError("Recorded charge exceeds the local reserve; stop and inspect locally.")
                try:
                    html = body.decode("utf-8")
                except UnicodeDecodeError:
                    raise AcquisitionError("Capture is not UTF-8; adapter validation is required.") from None
                return html, {"observed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                              "source_url": target, "browser": browser, "proxy_type": "datacenter", "proxy_country": "us",
                              "timeout": 30, "return_page_source": False, "attempts": attempt, "pages": 1,
                              "credits_recorded": cost, "credit_reserve": per_attempt * max_attempts,
                              "accepted_snapshot": False, "adapter_validation_required": True}
        except HTTPError as exc:
            # Only retry an explicit transient server error; do not replay a
            # timeout or free-plan overlap whose remote completion is unknown.
            if exc.code == 500 and attempt < max_attempts:
                pause(1)
                continue
            raise AcquisitionError("API request failed (HTTP %s); no snapshot accepted." % exc.code) from None
        except (URLError, TimeoutError, OSError):
            raise AcquisitionError("Network failure; remote completion unknown. Stop before retrying.") from None
    raise AcquisitionError("Attempt cap reached.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--browser", required=True, choices=("true", "false"))
    parser.add_argument("--permitted", required=True, action="store_true", help="Confirm you may retrieve this target.")
    parser.add_argument("--max-attempts", type=int, default=1, choices=(1, 2))
    parser.add_argument("--max-credits", type=int, default=10)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        # Reserve a new directory and both output files before any provider call.
        # Its parent must already exist; never overwrite an earlier capture.
        args.out.mkdir(exist_ok=False)
        with (args.out / "capture.html").open("x", encoding="utf-8") as html_file, (args.out / "provenance.json").open("x", encoding="utf-8") as provenance_file:
            html, metadata = fetch_html(args.url, args.browser == "true", args.max_attempts, args.max_credits)
            html_file.write(html)
            provenance_file.write(json.dumps(metadata, indent=2) + "\n")
        print("Saved one local HTML capture and provenance; validate the source adapter before comparison.")
    except (AcquisitionError, OSError) as exc:
        # Never print arbitrary OS paths, upstream response bodies or URLs.
        print(str(exc) if isinstance(exc, AcquisitionError) else "Local capture could not be saved.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
