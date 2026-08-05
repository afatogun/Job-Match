"""Filesystem paths and environment configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def _resolve_data_dir() -> Path:
    configured = os.getenv("JOBMATCH_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (PROJECT_ROOT / "data").resolve()


DATA_DIR = _resolve_data_dir()
UPLOADS_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
PROFILES_DIR = DATA_DIR / "profiles"
DB_PATH = DATA_DIR / "jobmatch.db"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Storage controls for constrained instances (e.g., micro EC2).
AUTO_CLEANUP_ON_START = _bool_env("JOBMATCH_AUTO_CLEANUP_ON_START", True)
VACUUM_ON_CLEANUP = _bool_env("JOBMATCH_VACUUM_ON_CLEANUP", True)
RETENTION_REFRESH_RUNS_DAYS = _int_env("JOBMATCH_RETENTION_REFRESH_RUNS_DAYS", 30)
RETENTION_GENERATED_DAYS = _int_env("JOBMATCH_RETENTION_GENERATED_DAYS", 21)
RETENTION_UPLOADS_DAYS = _int_env("JOBMATCH_RETENTION_UPLOADS_DAYS", 14)


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, GENERATED_DIR, PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")
