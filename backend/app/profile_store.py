"""The single candidate profile, stored as data/profile.json.

One user, one profile - deliberately a JSON file rather than relational tables.
"""

import json
import logging
from datetime import datetime, timezone

from .config import DATA_DIR, ensure_dirs
from .models import Profile

log = logging.getLogger(__name__)

PROFILE_PATH = DATA_DIR / "profile.json"


def load_profile() -> Profile | None:
    if not PROFILE_PATH.exists():
        return None
    try:
        return Profile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        log.warning("profile.json unreadable (%s); treating as absent", exc)
        return None


def save_profile(profile: Profile) -> Profile:
    ensure_dirs()
    profile.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    PROFILE_PATH.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def profile_exists() -> bool:
    return PROFILE_PATH.exists()
