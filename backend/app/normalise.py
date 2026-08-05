"""Data hygiene: scraped values -> clean, comparable, storable values."""

import hashlib
import math
import re
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that identify a posting are kept; these only track the referrer.
# Indeed encodes the job id as ?jk=... so the query string must never be dropped wholesale.
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "from",
    "tk",
    "advn",
    "adid",
    "pub",
    "vjs",
    "vjk",
    "trk",
    "trackingid",
    "refresh",
    "source",
    "sid",
    "gclid",
}

# "Dublin, D, IE" -> the middle token is a state/county code we don't want to show.
COUNTRY_NAMES = {
    "IE": "Ireland",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "US": "United States",
    "USA": "United States",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "IN": "India",
    "CN": "China",
}

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def clean_value(v):
    """Scalar from a pandas row -> plain Python value, with NaN/NaT collapsed to None.

    Applied per field rather than via df.fillna(), which would coerce numeric
    salary columns into strings.
    """
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    # pandas NaT and other null-likes
    try:
        import pandas as pd

        if not isinstance(v, (list, tuple, dict, set)) and pd.isna(v):
            return None
    except (TypeError, ValueError, ImportError):
        pass
    return v


def clean_str(v) -> str | None:
    v = clean_value(v)
    if v is None:
        return None
    return str(v).strip() or None


def clean_float(v) -> float | None:
    v = clean_value(v)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def clean_bool(v) -> bool | None:
    v = clean_value(v)
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes"}
    return bool(v)


def clean_date(v) -> str | None:
    """-> ISO YYYY-MM-DD, or None."""
    v = clean_value(v)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    text = str(v).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def clean_location(v) -> str | None:
    """'Dublin, D, IE' -> 'Dublin, Ireland'."""
    text = clean_str(v)
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None
    out: list[str] = []
    for part in parts:
        upper = part.upper()
        if upper in COUNTRY_NAMES:
            out.append(COUNTRY_NAMES[upper])
        elif len(part) <= 2 and part.isalpha():
            # Bare state/county code ("Dublin, D, IE"). Meaningless on its own,
            # and dropped in any position so it never renders as "CN, Ireland".
            continue
        else:
            out.append(part)
    return ", ".join(dict.fromkeys(out)) or None


def norm_text(v: str | None) -> str:
    """Lowercase, punctuation-free, single-spaced - for comparison only."""
    if not v:
        return ""
    return _WS.sub(" ", _NON_ALNUM.sub(" ", v.lower())).strip()


def canonical_url(url: str | None) -> str | None:
    """Drop tracking params and fragments; keep identifying params such as Indeed's ?jk."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip() or None
    if not parts.scheme and not parts.netloc:
        return url.strip() or None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in TRACKING_PARAMS]
    query.sort()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def content_key(company: str | None, title: str | None, location: str | None) -> str:
    """Identity of the vacancy itself, independent of which board it came from."""
    basis = "|".join((norm_text(company), norm_text(title), norm_text(location)))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def dedup_key(source: str, source_job_id: str | None, job_url: str | None, fallback: str) -> str:
    """Strongest available identity for a posting."""
    if source_job_id:
        basis = f"{source}:{source_job_id}"
    else:
        canon = canonical_url(job_url)
        basis = f"url:{canon}" if canon else f"content:{fallback}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()
