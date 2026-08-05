"""Search settings persist as JSON blobs keyed by profile_id.

Legacy: a single global row (search_settings id=1) is used as fallback if no
per-profile settings exist yet, preserving existing data across the upgrade.
"""

import json
from datetime import datetime, timezone

from .db import connect
from .models import SearchSettings


def _active_id() -> str | None:
    from .profile_store import active_profile_id  # late import avoids any startup ordering issues
    return active_profile_id()


def load_settings(profile_id: str | None = None) -> SearchSettings:
    pid = profile_id or _active_id()
    with connect() as conn:
        row = None
        if pid:
            row = conn.execute(
                "SELECT json FROM profile_settings WHERE profile_id = ?", (pid,)
            ).fetchone()
        if not row:
            # Fall back to legacy global settings row
            row = conn.execute("SELECT json FROM search_settings WHERE id = 1").fetchone()
    if not row:
        return SearchSettings()
    try:
        return SearchSettings.model_validate(json.loads(row["json"]))
    except (json.JSONDecodeError, ValueError):
        return SearchSettings()


def save_settings(settings: SearchSettings, profile_id: str | None = None) -> SearchSettings:
    pid = profile_id or _active_id()
    payload = settings.model_dump_json()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        if pid:
            conn.execute(
                """
                INSERT INTO profile_settings (profile_id, json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET json = excluded.json, updated_at = excluded.updated_at
                """,
                (pid, payload, now),
            )
        else:
            # No profiles created yet — write to legacy global slot
            conn.execute(
                """
                INSERT INTO search_settings (id, json, updated_at) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET json = excluded.json, updated_at = excluded.updated_at
                """,
                (payload, now),
            )
    return settings
