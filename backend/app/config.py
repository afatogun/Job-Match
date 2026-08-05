"""Filesystem paths and environment configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
DB_PATH = DATA_DIR / "jobmatch.db"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, GENERATED_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")


def set_openai_key(key: str) -> None:
    """Persist the key to .env. Not used until step 13 (OpenAI ranking)."""
    key = key.strip()
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = [
            ln
            for ln in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if not ln.startswith("OPENAI_API_KEY=")
        ]
    if key:
        lines.append(f"OPENAI_API_KEY={key}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = key
