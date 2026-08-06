# Job-Match — Agent Instructions

Single-user local app: job scraping → local + AI ranking → tailored CV/cover-letter generation → DOCX/PDF export. See [README.md](README.md) for full feature description.

## Dev Commands

```powershell
# Start both servers (two new windows)
.\dev.ps1

# Backend only
cd backend; uv run uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend; npm run dev

# Smoke-test a job source directly
cd backend; uv run python -m app.scripts.smoke_indeed
```

**Backend:** http://127.0.0.1:8000 · API docs at /docs
**Frontend:** http://localhost:5173

## Stack & Critical Constraints

- **Python 3.12 exactly** — `python-jobspy` pins `numpy==1.26.3` whose Windows wheels stop at cp312. Do not change `requires-python`.
- Backend: FastAPI + SQLite (WAL mode) + Pydantic v2 + OpenAI
- Frontend: React 19, React Router 7, TypeScript 5, Tailwind 4, Vite 7
- Package manager: `uv` (backend), `npm` (frontend)
- `.env` lives at repo root; `OPENAI_API_KEY` is the only env variable. Never commit real keys. See `.env.example`.

## Architecture

```
backend/app/
  main.py           FastAPI app, CORS for Vite, DB init lifespan
  db.py             SQLite helpers, idempotent migrations, 4 tables
  models.py         Pydantic models — Job, Profile, Application, SearchSettings, Augmentation
  config.py         Paths (DATA_DIR, DB_PATH, UPLOADS_DIR, GENERATED_DIR), .env loading
  pipeline.py       collect → normalise → filter → score → dedup → store → rank
  scoring.py        Local relevance score (0–100): title 45% / keywords 25% / location 10% / freshness 12% / seniority 8%
  ranking.py        Batched AI ranking (8 jobs/call), structured output → JSON fallback
  gap_analysis.py   Vacancy requirement extraction + profile diff, feeds CV generation
  generation.py     Augmentation policy + human-style enforcement (50+ banned ML buzzwords)
  documents.py      DOCX rendering (Calibri 10.5pt, ATS-safe) + LibreOffice/Word PDF export
  applications.py   Orchestrates generation; bulk run state via in-memory lock
  cv_import.py      PDF/DOCX/TXT → plain text → OpenAI → Profile
  profile_store.py  data/profile.json read/write
  settings_store.py SearchSettings in SQLite search_settings table (id=1)
  humanize.py       Post-generation text cleanup
  normalise.py      Whitespace/encoding normalisation for scraped text
  ai.py             OpenAI client wrapper
  routers/          One router per domain (jobs, profile, settings, applications)
  sources/          One module per job board; extend here
```

### Data storage

| What | Where | Format |
|---|---|---|
| Jobs & applications | `data/jobmatch.db` (SQLite) | Rows; dedup by `dedup_key` (source ID) + `content_key` (hash) |
| Search settings | Same DB, `search_settings` table, id=1 | JSON blob |
| User profile | `data/profile.json` | Pydantic model dump |
| OpenAI key | `.env` at repo root | Env var |
| Generated docs | `data/generated/{company}-{role}-{job_id}/` | DOCX + PDF |
| CV uploads | `data/uploads/` | Binary archive |

## Key Conventions

### Adding a job source
1. Create `backend/app/sources/my_source.py` implementing the `JobSource` protocol (`__call__(settings, search_term) -> SourceResult`) and the `RawJob` dataclass from `sources/base.py`.
2. Register in `sources/registry.py` (label + optional `unreliable` flag).
That's it — the pipeline picks it up automatically.

### Background tasks
Refresh and bulk generation run on worker threads. In-memory state objects (`RefreshStatus`, `GenerationStatus`) use threading locks. The UI polls `/api/jobs/refresh` every 1.5 s and `/api/generate/bulk/status` every 2 s.

### AI ranking scope
AI ranking only runs on jobs that pass a local-score threshold (set in SearchSettings). Batched at 8 jobs/call for cost efficiency. Prompt instructs: "scores above 85 should be rare, judge on evidence only."

### Augmentation levels
Defined as `AUGMENTATION_POLICY` in `generation.py`. Every level uses the same six headings (`WHAT YOU MAY DO` / `WHAT YOU MAY NEVER DO` / `METRICS` / `JOB TITLES` / `PROJECTS AND EDUCATION` / `FLAGGING`) so a rule can never be silently absent. The policy leads the system prompt and explicitly overrides everything after it — `CV_CRAFT` is level-agnostic on purpose, because the old assembly stated absolute prohibitions ahead of the permission meant to override them.

| Level | May do | May never do |
|---|---|---|
| `accurate` | Reword, reorder, drop. | Add anything not in the profile. Numbers must already be in the profile. |
| `enhanced` | Reframe toward the vacancy, make explicit the skills the real work implies. | Name a system the profile does not mention. New numbers. Retitle roles. |
| `aggressive` | Name initiatives/systems under real employers, state calibrated metrics, reframe titles toward the vacancy at the same seniority. | Add or rename an employer. Change dates. Inflate seniority. Add Projects entries, degrees or certifications. |

**No level may invent employers, change employment dates, or add education.** `aggressive` may state metrics and named systems; `accurate` and `enhanced` may not. Anything asserted beyond the profile is marked `inferred=true` and listed in `flagged_additions` for the review panel. Under `aggressive`, `inferred` marks only invented specifics, not reworded real work, or the panel becomes noise.

### Gap analysis (`gap_analysis.py`)
`enhanced` and `aggressive` run a first pass (`analyse_gap`) that extracts the vacancy's requirements and diffs them against the profile before any CV is written, because one call asked to do both defaults to restating the profile. It is level-independent by design; `filter_for_level` narrows it in Python, which is what lets one cached analysis serve all three levels. Cached on the `applications` row keyed by `sha256(description + profile.updated_at)`. `accurate` never sees it. The call is wrapped in try/except — a failure degrades to single-pass generation, never a failed pack.

### Frontend–backend sync
Types in `frontend/src/types.ts` mirror backend Pydantic models. Keep them in sync manually when changing models. All API calls go through the singleton `api` object in `frontend/src/api.ts`.

### Display score
`DISPLAY_SCORE = COALESCE(ai_score, local_score)` — computed at query time in `routers/jobs.py`. "Good match" threshold is 70.

## Common Pitfalls

- **Do not upgrade Python** past 3.12 — see constraint above.
- **No test suite** — validate changes manually or via the smoke script.
- `data/` is gitignored. Do not assume it exists; the lifespan hook creates it.
- PDF export is best-effort (requires LibreOffice or Word). Don't error if unavailable.
- DOCX rendering is ATS-safe: no tables, text boxes, or icons. Keep it that way.
- The `.env` file is at the **repo root**, not inside `backend/`.
