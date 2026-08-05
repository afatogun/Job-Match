"""Step 12 - master CV upload and the editable structured profile."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..ai import MissingAPIKey
from ..config import UPLOADS_DIR, ensure_dirs
from ..cv_import import extract_text, structure_cv
from ..models import Profile
from ..profile_store import load_profile, save_profile
from ..settings_store import load_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("")
def read_profile() -> dict:
    profile = load_profile()
    return {"exists": profile is not None, "profile": profile}


@router.put("", response_model=Profile)
def write_profile(profile: Profile) -> Profile:
    return save_profile(profile)


@router.post("/upload", response_model=Profile)
async def upload_cv(file: UploadFile = File(...)) -> Profile:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File is larger than 10 MB")

    filename = file.filename or "master-cv"

    ensure_dirs()
    try:
        (UPLOADS_DIR / filename).write_bytes(data)
    except OSError as exc:
        log.warning("Could not archive upload: %s", exc)

    try:
        text = extract_text(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - corrupt file, bad encoding, etc.
        raise HTTPException(status_code=400, detail=f"Could not read that file: {exc}") from exc

    settings = load_settings()
    try:
        profile = structure_cv(text, settings.openai_model, filename)
    except MissingAPIKey as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    return save_profile(profile)


@router.get("/extract-preview")
def extract_preview() -> dict:
    """What text we read from the last upload - useful when extraction looks wrong."""
    profile = load_profile()
    return {"source_filename": profile.source_filename if profile else ""}
