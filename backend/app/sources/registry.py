"""The extension point for job sources.

Adding Glassdoor / JobsIreland / LinkedIn later = one module + one entry here.
The pipeline reads this map and needs no changes.
"""

from .base import JobSource
from . import indeed

SOURCES: dict[str, JobSource] = {
    indeed.SOURCE: indeed.fetch,
}

# Shown in the UI so labels stay consistent with the stored `source` value.
SOURCE_LABELS: dict[str, str] = {
    "indeed": "Indeed",
}


def get_source(name: str) -> JobSource | None:
    return SOURCES.get(name)


def label_for(name: str) -> str:
    return SOURCE_LABELS.get(name, name.title())
