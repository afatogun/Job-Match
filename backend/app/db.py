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

-- One generated application pack per job.
CREATE TABLE IF NOT EXISTS applications (
    id                INTEGER PRIMARY KEY,
    job_id            INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    augmentation      TEXT NOT NULL DEFAULT 'enhanced',
    cv_json           TEXT,
    cover_letter_text TEXT,
    flagged_additions TEXT,
    folder            TEXT,
    cv_docx           TEXT,
    cv_pdf            TEXT,
    cover_letter_docx TEXT,
    model             TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);

-- Per-profile search settings (one row per profile).
CREATE TABLE IF NOT EXISTS profile_settings (
    profile_id TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Columns added after the first release. Applied idempotently on startup so an
# existing jobmatch.db keeps its data.
MIGRATIONS: list[tuple[str, str]] = [
    ("jobs", "local_score REAL"),
    ("jobs", "ai_score REAL"),
    ("jobs", "ai_reason TEXT"),
    ("jobs", "ai_matching_skills TEXT"),
    ("jobs", "ai_missing_skills TEXT"),
    ("jobs", "ai_seniority_fit TEXT"),
    ("jobs", "ai_ranked_at TEXT"),
    ("jobs", "matching_terms TEXT"),
    ("jobs", "profile_id TEXT"),
    ("applications", "profile_id TEXT"),
    ("applications", "stage TEXT DEFAULT 'generated'"),
    ("applications", "stage_updated_at TEXT"),
    ("applications", "interview_prep_json TEXT"),
    ("applications", "interview_prep_generated_at TEXT"),
    # Vacancy gap analysis, cached per job. The key is a hash of the description and the
    # profile's updated_at, so it survives regeneration at a different augmentation level
    # but is invalidated when either input actually changes.
    ("applications", "gap_analysis_json TEXT"),
    ("applications", "gap_analysis_key TEXT"),
    ("applications", "gap_analysis_generated_at TEXT"),
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for table, column_def in MIGRATIONS:
        column = column_def.split()[0]
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def init_db() -> None:
    ensure_dirs()
    with connect() as conn:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)
