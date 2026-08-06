"""Search settings endpoints."""

from fastapi import APIRouter, Query

from ..maintenance import cleanup_storage
from ..models import SearchSettings
from ..settings_store import load_settings, save_settings
from ..sources.registry import SOURCE_LABELS

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SearchSettings)
def read_settings(profile_id: str | None = Query(default=None)) -> SearchSettings:
    return load_settings(profile_id)


@router.put("", response_model=SearchSettings)
def write_settings(settings: SearchSettings, profile_id: str | None = Query(default=None)) -> SearchSettings:
    return save_settings(settings, profile_id)


@router.get("/sources")
def available_sources() -> list[dict[str, str]]:
    return [{"name": name, "label": label} for name, label in SOURCE_LABELS.items()]


@router.get("/countries")
def available_countries() -> list[dict[str, str]]:
    from jobspy.model import Country  # lazy: importing jobspy pulls in pandas

    skip = {"US_CANADA", "WORLDWIDE"}  # internal ziprecruiter/linkedin placeholders, not real countries
    out = []
    for member in Country:
        if member.name in skip:
            continue
        aliases = [a.strip() for a in member.value[0].split(",") if a.strip()]
        out.append({"value": aliases[0], "label": max(aliases, key=len).title()})
    out.sort(key=lambda c: c["label"])
    return out


@router.post("/maintenance/cleanup")
def run_storage_cleanup() -> dict[str, int | bool]:
    return cleanup_storage()
