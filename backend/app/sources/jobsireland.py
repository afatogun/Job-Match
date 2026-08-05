"""JobsIreland (jobsireland.ie) via httpx + BeautifulSoup.

LIMITATION - please read before extending this.

The site's server-rendered page only ever returns the ~11 most recently published
vacancies. Everything else is client-side JavaScript:

  * any query parameter (keyWord, location, page) makes the server render
    "No jobs match this search" with totalCount=0
  * pagination anchors are literally href="Javascript:void(0)"
  * /en-US/job-Details?id=... returns HTTP 500 to non-browser clients,
    so descriptions cannot be fetched

So this source contributes only the newest handful of national vacancies, which we
filter locally against the search term. Those listings are dominated by Community
Employment schemes and general/hospitality roles, so for software and AI positions
it will usually contribute nothing. It is registered but off by default.

Getting real search out of this site would require driving a browser (Playwright),
which the brief asks us to avoid unless absolutely necessary. Indeed and Glassdoor
carry the actual job discovery.
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup

from ..models import SearchSettings
from ..normalise import clean_date, clean_str, norm_text
from .base import RawJob, SourceResult

log = logging.getLogger(__name__)

SOURCE = "jobsireland"
BASE_URL = "https://www.jobsireland.ie/en-US/browse-jobs"
DETAIL_URL = "https://www.jobsireland.ie/en-US/job-Details?id={id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-IE,en;q=0.9",
}

_LOGO_ALT = re.compile(r"^Logo of\s+(.*)$", re.I)


def _hidden(card, field_id: str) -> str | None:
    el = card.select_one(f'input[id="{field_id}"]')
    return clean_str(el.get("value")) if el else None


def _company(card) -> str | None:
    """The company name only appears in the logo's alt text on this site."""
    for img in card.select("img[alt]"):
        m = _LOGO_ALT.match(img.get("alt", "").strip())
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def _parse_card(card) -> RawJob | None:
    job_id = _hidden(card, "JobId") or card.get("data-vacancyid")
    title = _hidden(card, "JobTitle")
    if not job_id or not title:
        return None

    return RawJob(
        source=SOURCE,
        source_job_id=str(job_id),
        title=title,
        company=_company(card),
        location=_hidden(card, "Location"),
        job_url=DETAIL_URL.format(id=job_id),
        # The site has no separate employer link, and detail pages 500 for us.
        job_url_direct=None,
        date_posted=clean_date((_hidden(card, "StartDate") or "")[:10]),
        description=None,
        raw={
            "reference": _hidden(card, "JobReference") or "",
            "closing_date": (_hidden(card, "EndDate") or "")[:10],
        },
    )


def _matches(job: RawJob, search_term: str) -> bool:
    """Local filtering - the site's own search returns nothing for us."""
    if not search_term.strip():
        return True
    title = norm_text(job.title)
    # Any meaningful word from the search term appearing in the title is enough;
    # the pool is tiny, so being generous here costs nothing.
    words = [w for w in norm_text(search_term).split() if len(w) > 2]
    return any(w in title for w in words) if words else True


def fetch(settings: SearchSettings, search_term: str) -> SourceResult:
    """Never raises - failures come back as ok=False."""
    try:
        resp = httpx.get(BASE_URL, headers=HEADERS, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - must not stop other sources
        log.warning("JobsIreland fetch failed for %r: %s", search_term, exc)
        return SourceResult(SOURCE, search_term, ok=False, error=f"{type(exc).__name__}: {exc}")

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs: list[RawJob] = []
        for card in soup.select("div.job-heading"):
            job = _parse_card(card)
            if job and _matches(job, search_term):
                jobs.append(job)
    except Exception as exc:  # noqa: BLE001 - markup changes shouldn't crash a run
        log.warning("JobsIreland parse failed for %r: %s", search_term, exc)
        return SourceResult(SOURCE, search_term, ok=False, error=f"parse error: {exc}")

    log.info("JobsIreland %r -> %d jobs (of %d recent)", search_term, len(jobs),
             len(soup.select("div.job-heading")))
    return SourceResult(SOURCE, search_term, ok=True, jobs=jobs)
