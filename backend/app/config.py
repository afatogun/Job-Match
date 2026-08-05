"""Filesystem paths and environment configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
PROFILES_DIR = DATA_DIR / "profiles"
DB_PATH = DATA_DIR / "jobmatch.db"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, GENERATED_DIR, PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")
