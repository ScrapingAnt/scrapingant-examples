"""Complete no-secret example: seed, save scoped cookies, restore and extract."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from requests import Session
from catalog_fixture import CatalogFixture
from cookie_state import load_jar, save_private_jar
from oracle import score
from requests_matrix import environment


def main():
    with CatalogFixture() as fixture, tempfile.TemporaryDirectory(prefix="requests-cookie-demo-") as tmp:
        snapshot = Path(tmp) / "cookies.lwp"
        with Session() as first:
            first.trust_env = False  # The local demo ignores ambient proxies/.netrc.
            final = first.get(fixture.base_url + "/login", timeout=5)
            final.raise_for_status()
            accumulation = {
                "redirect_responses": len(final.history),
                "final_response_cookies": len(final.cookies),
                "accumulated_session_cookies": len(first.cookies),
            }
            # New-file only; opt in to saving otherwise-discarded session cookies.
            save_private_jar(first.cookies, snapshot, include_session=True)
        with Session() as restored:
            restored.trust_env = False
            # Opt in at load too. Expired cookies remain excluded at both steps.
            restored.cookies = load_jar(snapshot, include_session=True)
            response = restored.get(fixture.base_url + "/catalog/eu/products", timeout=5)
            response.raise_for_status()
            records = response.json()["records"]
            result = {
                "tested_at": datetime.now(timezone.utc).isoformat(),
                "environment": environment(), "cookie_accumulation": accumulation,
                "restored_cookie_count": len(restored.cookies),
                "status": response.status_code, "records": records, **score(records),
            }
            assert result["exact_match"], "The records differ from the literal expected dataset"
            print(json.dumps(result, indent=2))  # Records and counts; no cookie values.


if __name__ == "__main__":
    main()
