"""Proof that a source returns genuine live data, independent of the app.

    uv run python -m app.scripts.smoke_indeed
    uv run python -m app.scripts.smoke_indeed "Backend Engineer"
    uv run python -m app.scripts.smoke_indeed "AI Engineer" glassdoor
"""

import logging
import sys

from ..models import SearchSettings
from ..settings_store import load_settings
from ..sources.registry import get_source

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def main() -> int:
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001 - DB may not exist yet
        settings = SearchSettings()

    term = sys.argv[1] if len(sys.argv) > 1 else settings.target_titles[0]
    source_name = sys.argv[2] if len(sys.argv) > 2 else "indeed"
    settings.results_per_title = min(settings.results_per_title, 10)

    source = get_source(source_name)
    if source is None:
        print(f"Unknown source {source_name!r}")
        return 1

    print(f"Searching {source_name} for {term!r} in {settings.location!r} "
          f"(last {settings.max_job_age_days} days)\n")

    result = source(settings, term)
    if not result.ok:
        print(f"FAILED: {result.error}")
        return 1

    if not result.jobs:
        print("No jobs returned. Try a different location, e.g. 'Dublin, Ireland'.")
        return 1

    for job in result.jobs[:5]:
        salary = ""
        if job.salary_min or job.salary_max:
            salary = (f" | {job.salary_currency or ''}{job.salary_min or '?'}-"
                      f"{job.salary_max or '?'} {job.salary_interval or ''}")
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
