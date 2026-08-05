"""Candidate profiles stored in data/profiles/.

Multiple profiles are supported; one is active at a time.
The active profile is used by generation and ranking.
Existing data/profile.json is auto-migrated to a "Default" profile on first access.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import PROFILES_DIR
from .models import Profile, ProfileMeta

log = logging.getLogger(__name__)

_META_FILE = PROFILES_DIR / "meta.json"
_LEGACY_PATH = PROFILES_DIR.parent / "profile.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _migrate_legacy() -> None:
    """One-time migration: data/profile.json → a Default profile entry."""
    if _META_FILE.exists() or not _LEGACY_PATH.exists():
        return
    _ensure()
    pid = str(uuid.uuid4())
    try:
        raw = _LEGACY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        src = data.get("source_filename")
    except Exception:  # noqa: BLE001
        raw, src = "{}", None
    (PROFILES_DIR / f"{pid}.json").write_text(raw, encoding="utf-8")
    _save_meta({"active_id": pid, "profiles": [
        {"id": pid, "name": "Default", "created_at": _now(), "source_filename": src}
    ]})
    log.info("Migrated legacy profile.json → profile %s (Default)", pid)


def _load_meta() -> dict:
    _migrate_legacy()
    if not _META_FILE.exists():
        return {"active_id": None, "profiles": []}
    try:
        return json.loads(_META_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("profiles/meta.json unreadable (%s); using empty state", exc)
        return {"active_id": None, "profiles": []}


def _save_meta(meta: dict) -> None:
    _ensure()
    _META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ multi-profile API


def list_profiles() -> list[ProfileMeta]:
    meta = _load_meta()
    active_id = meta.get("active_id")
    return [ProfileMeta(is_active=(p["id"] == active_id), **p) for p in meta.get("profiles", [])]


def create_profile(name: str) -> ProfileMeta:
    _ensure()
    pid = str(uuid.uuid4())
    entry = {"id": pid, "name": name, "created_at": _now(), "source_filename": None}
    meta = _load_meta()
    meta["profiles"].append(entry)
    if not meta.get("active_id"):
        meta["active_id"] = pid
    _save_meta(meta)
    (PROFILES_DIR / f"{pid}.json").write_text("{}", encoding="utf-8")
    return ProfileMeta(is_active=(meta["active_id"] == pid), **entry)


def delete_profile(profile_id: str) -> None:
    meta = _load_meta()
    if len(meta.get("profiles", [])) <= 1:
        raise ValueError("Cannot delete the only profile")
    meta["profiles"] = [p for p in meta["profiles"] if p["id"] != profile_id]
    if meta.get("active_id") == profile_id:
        meta["active_id"] = meta["profiles"][0]["id"] if meta["profiles"] else None
    _save_meta(meta)
    path = PROFILES_DIR / f"{profile_id}.json"
    if path.exists():
        path.unlink()


def set_active_profile(profile_id: str) -> None:
    meta = _load_meta()
    if not any(p["id"] == profile_id for p in meta.get("profiles", [])):
        raise ValueError(f"Profile {profile_id!r} not found")
    meta["active_id"] = profile_id
    _save_meta(meta)


def rename_profile(profile_id: str, name: str) -> ProfileMeta:
    meta = _load_meta()
    for p in meta.get("profiles", []):
        if p["id"] == profile_id:
            p["name"] = name
            _save_meta(meta)
            return ProfileMeta(is_active=(meta.get("active_id") == profile_id), **p)
    raise ValueError(f"Profile {profile_id!r} not found")


def load_profile_by_id(profile_id: str) -> Profile | None:
    path = PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return None
    try:
        return Profile.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        log.warning("Profile %s unreadable (%s)", profile_id, exc)
        return None


def save_profile_by_id(profile_id: str, profile: Profile) -> Profile:
    _ensure()
    profile.updated_at = _now()
    (PROFILES_DIR / f"{profile_id}.json").write_text(
        profile.model_dump_json(indent=2), encoding="utf-8"
    )
    meta = _load_meta()
    for p in meta.get("profiles", []):
        if p["id"] == profile_id:
            p["source_filename"] = profile.source_filename
            break
    _save_meta(meta)
    return profile


# ------------------------------------------------------------------ backward-compatible API
# Called by applications.py, ranking.py, and routers/profile.py — must not break.


def active_profile_id() -> str | None:
    """Return the currently active profile's ID, or None if no profiles exist."""
    return _load_meta().get("active_id")


def load_profile() -> Profile | None:
    """Load the currently active profile."""
    meta = _load_meta()
    pid = meta.get("active_id")
    return load_profile_by_id(pid) if pid else None


def save_profile(profile: Profile) -> Profile:
    """Save to the currently active profile, creating a Default profile if none exists."""
    meta = _load_meta()
    pid = meta.get("active_id")
    if not pid:
        pid = create_profile("Default").id
    return save_profile_by_id(pid, profile)


def profile_exists() -> bool:
    return load_profile() is not None
