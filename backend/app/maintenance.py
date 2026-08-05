"""Storage maintenance for constrained deployments."""

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import (
    GENERATED_DIR,
    RETENTION_GENERATED_DAYS,
    RETENTION_REFRESH_RUNS_DAYS,
    RETENTION_UPLOADS_DAYS,
    UPLOADS_DIR,
    VACUUM_ON_CLEANUP,
)
from .db import connect

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_cutoff(days: int) -> str:
    return (_now() - timedelta(days=days)).isoformat(timespec="seconds")


def _folder_mtime(folder: Path) -> datetime:
    try:
        mtime = folder.stat().st_mtime
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _prune_generated_folders(days: int) -> int:
    if days <= 0 or not GENERATED_DIR.exists():
        return 0

    cutoff = _now() - timedelta(days=days)
    deleted = 0
    for folder in GENERATED_DIR.iterdir():
        if not folder.is_dir():
            continue
        if _folder_mtime(folder) >= cutoff:
            continue
        try:
            shutil.rmtree(folder)
            deleted += 1
            with connect() as conn:
                conn.execute(
                    """
                    UPDATE applications
                       SET folder = NULL,
                           cv_docx = NULL,
                           cv_pdf = NULL,
                           cover_letter_docx = NULL,
                           updated_at = ?
                     WHERE folder = ?
                    """,
                    (_now().isoformat(timespec="seconds"), str(folder)),
                )
        except OSError as exc:
            log.warning("Could not remove generated folder %s: %s", folder, exc)
    return deleted


def _prune_uploads(days: int) -> int:
    if days <= 0 or not UPLOADS_DIR.exists():
        return 0

    cutoff = _now() - timedelta(days=days)
    deleted = 0
    for item in UPLOADS_DIR.iterdir():
        if not item.is_file():
            continue
        if _folder_mtime(item) >= cutoff:
            continue
        try:
            item.unlink()
            deleted += 1
        except OSError as exc:
            log.warning("Could not remove upload %s: %s", item, exc)
    return deleted


def _prune_refresh_runs(days: int) -> int:
    if days <= 0:
        return 0
    cutoff = _iso_cutoff(days)
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM refresh_runs WHERE started_at < ?",
            (cutoff,),
        )
    return cur.rowcount or 0


def cleanup_storage() -> dict[str, int | bool]:
    removed_refresh_rows = _prune_refresh_runs(RETENTION_REFRESH_RUNS_DAYS)
    removed_generated_folders = _prune_generated_folders(RETENTION_GENERATED_DAYS)
    removed_uploads = _prune_uploads(RETENTION_UPLOADS_DAYS)

    vacuumed = False
    if VACUUM_ON_CLEANUP:
        with connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        vacuumed = True

    summary: dict[str, int | bool] = {
        "removed_refresh_rows": removed_refresh_rows,
        "removed_generated_folders": removed_generated_folders,
        "removed_uploads": removed_uploads,
        "vacuumed": vacuumed,
    }
    log.info("Storage cleanup complete: %s", summary)
    return summary
