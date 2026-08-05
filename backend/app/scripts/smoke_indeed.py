"""Proof that genuine Indeed Ireland data comes back, independent of the app.

    uv run python -m app.scripts.smoke_indeed
"""

import logging
import sys

from ..models import SearchSettings
from ..settings_store import load_settings
from ..sources import indeed

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def main() -> int:
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001 - DB may not exist yet
        settings = SearchSettings()

    term = sys.argv[1] if len(sys.argv) > 1 else settings.target_titles[0]
    settings.results_per_title = min(settings.results_per_title, 10)

    print(f"Searching Indeed for {term!r} in {settings.location!r} "
          f"(last {settings.max_job_age_days} days)\n")

    result = indeed.fetch(settings, term)
    if not result.ok:
        print(f"FAILED: {result.error}")
        return 1

    if not result.jobs:
        print("No jobs returned. Try a different location, e.g. 'Dublin, Ireland'.")
        return 1

    for job in result.jobs[:5]:
        salary = ""
        if job.salary_min or job.salary_max:
            salary = f" | {job.salary_currency or ''}{job.salary_min or '?'}-{job.salary_max or '?'} {job.salary_interval or ''}"
        print(f"- {job.title}")
        print(f"  {job.company or 'Unknown company'} | {job.location or 'Unknown location'} "
              f"| posted {job.date_posted or 'unknown'}{salary}")
        print(f"  {job.job_url}")
        if job.job_url_direct:
            print(f"  direct: {job.job_url_direct}")
        print(f"  description: {len(job.description or '')} chars\n")

    print(f"{len(result.jobs)} jobs returned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
