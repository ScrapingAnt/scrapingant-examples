"""Schema for this owned employer fixture; not a universal ATS schema."""
from datetime import date, datetime, timezone
import re
from urllib.parse import urlsplit

FIELDS = ("jobID", "title", "employer", "location", "sourceURL", "applicationURL",
          "observedUTC", "sourcePostedDate")
CONTENT_FIELDS = tuple(field for field in FIELDS if field != "observedUTC")
ID_PATTERN = re.compile(r"NS-\d{3}\Z")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_record(record):
    """Return field errors rather than silently inventing missing values."""
    errors = []
    if set(record) != set(FIELDS):
        errors.append("record_keys")
    for field in FIELDS[:-1]:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(field)
    if not ID_PATTERN.fullmatch(str(record.get("jobID", ""))):
        errors.append("jobID")
    for field in ("sourceURL", "applicationURL"):
        try:
            value = urlsplit(record.get(field, ""))
            if (value.scheme not in ("http", "https") or not value.netloc or
                    value.username or value.password or value.fragment):
                errors.append(field)
        except ValueError:
            errors.append(field)
    value = record.get("observedUTC", "")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
            raise ValueError
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        errors.append("observedUTC")
    value = record.get("sourcePostedDate")
    if value is not None:
        try:
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError
        except ValueError:
            errors.append("sourcePostedDate")
    return sorted(set(errors))
