"""Step 12 - master CV upload and the editable structured profile."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..ai import MissingAPIKey
from ..config import PROFILES_DIR, UPLOADS_DIR, ensure_dirs
from ..cv_import import extract_text, structure_cv
from ..models import CreateProfileRequest, Profile, ProfileMeta, RenameProfileRequest
from ..profile_store import (
    create_profile,
    delete_profile,
    list_profiles,
    load_profile,
    load_profile_by_id,
    rename_profile,
    save_profile,
    save_profile_by_id,
    set_active_profile,
)
from ..settings_store import load_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])
profiles_router = APIRouter(prefix="/api/profiles", tags=["profiles"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


# ------------------------------------------------------------------ /api/profile (active profile)


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


# ------------------------------------------------------------------ /api/profiles (multi-profile)


@profiles_router.get("", response_model=list[ProfileMeta])
def list_profiles_endpoint() -> list[ProfileMeta]:
    return list_profiles()


@profiles_router.post("", response_model=ProfileMeta, status_code=201)
def create_profile_endpoint(payload: CreateProfileRequest) -> ProfileMeta:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Profile name cannot be empty")
    return create_profile(name)


@profiles_router.delete("/{profile_id}", status_code=204)
def delete_profile_endpoint(profile_id: str) -> None:
    try:
        delete_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@profiles_router.put("/{profile_id}/activate", response_model=list[ProfileMeta])
def activate_profile_endpoint(profile_id: str) -> list[ProfileMeta]:
    try:
        set_active_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return list_profiles()


@profiles_router.put("/{profile_id}/rename", response_model=ProfileMeta)
def rename_profile_endpoint(profile_id: str, payload: RenameProfileRequest) -> ProfileMeta:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Profile name cannot be empty")
    try:
        return rename_profile(profile_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@profiles_router.get("/{profile_id}")
def get_profile_by_id_endpoint(profile_id: str) -> dict:
    profile = load_profile_by_id(profile_id)
    return {"exists": profile is not None, "profile": profile}


@profiles_router.put("/{profile_id}", response_model=Profile)
def save_profile_by_id_endpoint(profile_id: str, profile: Profile) -> Profile:
    if load_profile_by_id(profile_id) is None and not (PROFILES_DIR / f"{profile_id}.json").exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    return save_profile_by_id(profile_id, profile)


@profiles_router.post("/{profile_id}/upload", response_model=Profile)
async def upload_cv_by_id_endpoint(profile_id: str, file: UploadFile = File(...)) -> Profile:
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
    except Exception as exc:  # noqa: BLE001
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

    return save_profile_by_id(profile_id, profile)
