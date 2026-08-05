"""SQLite access. One connection per operation - the refresh runs on a worker thread."""

import sqlite3

from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY,
    dedup_key       TEXT NOT NULL UNIQUE,
    content_key     TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_job_id   TEXT,
    title           TEXT NOT NULL,
    company         TEXT,
    location        TEXT,
    is_remote       INTEGER,
    job_url         TEXT NOT NULL,
    job_url_direct  TEXT,
    date_posted     TEXT,
    job_type        TEXT,
    salary_min      REAL,
    salary_max      REAL,
    salary_currency TEXT,
    salary_interval TEXT,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    relevance_score REAL,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    raw_json        TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_content_key  ON jobs(content_key);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted  ON jobs(date_posted DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status       ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_source       ON jobs(source);

CREATE TABLE IF NOT EXISTS search_settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id          INTEGER PRIMARY KEY,
    run_id      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source      TEXT NOT NULL,
    search_term TEXT NOT NULL,
    ok          INTEGER NOT NULL,
    found       INTEGER NOT NULL DEFAULT 0,
    inserted    INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_refresh_runs_started ON refresh_runs(started_at DESC);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db() -> None:
    ensure_dirs()
    with connect() as conn:
        conn.executescript(SCHEMA)
