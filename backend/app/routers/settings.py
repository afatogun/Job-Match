"""Search settings and the (not-yet-used) OpenAI key slot."""

from fastapi import APIRouter

from ..config import get_openai_key, set_openai_key
from ..models import OpenAIKeyUpdate, SearchSettings
from ..settings_store import load_settings, save_settings
from ..sources.registry import SOURCE_LABELS

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SearchSettings)
def read_settings() -> SearchSettings:
    return load_settings()


@router.put("", response_model=SearchSettings)
def write_settings(settings: SearchSettings) -> SearchSettings:
    return save_settings(settings)


@router.get("/sources")
def available_sources() -> list[dict[str, str]]:
    return [{"name": name, "label": label} for name, label in SOURCE_LABELS.items()]


@router.get("/openai")
def read_openai_key() -> dict[str, object]:
    """Never returns the key itself - only whether one is configured."""
    key = get_openai_key()
    return {"configured": bool(key), "masked": f"****{key[-4:]}" if len(key) > 4 else ""}


@router.put("/openai")
def write_openai_key(payload: OpenAIKeyUpdate) -> dict[str, object]:
    set_openai_key(payload.api_key)
    key = get_openai_key()
    return {"configured": bool(key), "masked": f"****{key[-4:]}" if len(key) > 4 else ""}
