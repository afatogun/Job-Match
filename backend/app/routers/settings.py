"""Search settings endpoints."""

from fastapi import APIRouter, Query

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


@router.put("", response_model=SearchSettings)
def write_settings(settings: SearchSettings) -> SearchSettings:
    return save_settings(settings)


@router.get("/sources")
def available_sources() -> list[dict[str, str]]:
    return [{"name": name, "label": label} for name, label in SOURCE_LABELS.items()]
