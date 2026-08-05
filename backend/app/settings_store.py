"""Search settings persist as a single JSON blob - no relational settings tables."""

import json
from datetime import datetime, timezone

from .db import connect
from .models import SearchSettings


def load_settings() -> SearchSettings:
    with connect() as conn:
        row = conn.execute("SELECT json FROM search_settings WHERE id = 1").fetchone()
    if not row:
        return SearchSettings()
    try:
        return SearchSettings.model_validate(json.loads(row["json"]))
    except (json.JSONDecodeError, ValueError):
        # A malformed blob should not brick the app; fall back to defaults.
        return SearchSettings()


def save_settings(settings: SearchSettings) -> SearchSettings:
    payload = settings.model_dump_json()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO search_settings (id, json, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET json = excluded.json, updated_at = excluded.updated_at
            """,
            (payload, now),
        )
    return settings
