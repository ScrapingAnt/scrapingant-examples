"""Replay a retained projection from one public GET; never fetches a live feed.

This is a separate Greenhouse list adapter, with no invented pagination interface.
The retained list lacks a separately verified application URL, so these are
candidates and are not passed to the HTML collector's validated refresh sink.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

CAPTURE_PATH = Path(__file__).parent / "fixtures/greenhouse-jobs-projection.json"
SOURCE = "https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs"


def project_capture(payload, *, employer):
    if not isinstance(employer, str) or not employer.strip():
        raise ValueError("employer label must be supplied and verified by caller")
    capture = payload.get("capture", {})
    jobs = payload.get("jobs")
    if (capture.get("url") != SOURCE or capture.get("status") != 200 or
            not isinstance(jobs, list) or capture.get("source_meta", {}).get("total") != len(jobs) or
            capture.get("jobs_count") != len(jobs)):
        raise ValueError("invalid captured list envelope or count")
    stamp = datetime.fromisoformat(capture["observed_utc"])
    if stamp.tzinfo is None:
        raise ValueError("capture observation needs a timezone")
    observed = stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    candidates, seen = [], set()
    for raw in jobs:
        job_id = raw.get("id")
        if not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0 or job_id in seen:
            raise ValueError("invalid or duplicate job post id")
        seen.add(job_id)
        title, location, url = raw.get("title"), raw.get("location", {}).get("name"), raw.get("absolute_url")
        if any(not isinstance(value, str) or not value.strip() for value in (title, location, url)):
            raise ValueError("missing listing field")
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.netloc != "job-boards.greenhouse.io" or
                parts.path != f"/greenhouse/jobs/{job_id}" or parts.fragment):
            raise ValueError("unexpected public job URL")
        updated = raw.get("updated_at")
        if not isinstance(updated, str) or datetime.fromisoformat(updated).tzinfo is None:
            raise ValueError("invalid source update timestamp")
        candidates.append({"jobID": str(job_id), "title": title.strip(), "employer": employer.strip(),
                           "location": location.strip(), "sourceURL": url, "applicationURL": None,
                           "observedUTC": observed, "sourcePostedDate": None,
                           "source_updated_at": updated})
    return {"source": SOURCE, "observedUTC": observed, "candidate_count": len(candidates),
            "validated_for_refresh": False, "missing_required_fields": ["applicationURL"],
            "candidate_records": sorted(candidates, key=lambda row: row["jobID"])}


if __name__ == "__main__":
    print(json.dumps(project_capture(json.loads(CAPTURE_PATH.read_text()), employer="Greenhouse"),
                     indent=2, sort_keys=True))
