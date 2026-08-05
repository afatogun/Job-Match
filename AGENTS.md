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
  generation.py     Augmentation rules + human-style enforcement (50+ banned ML buzzwords)
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
`accurate` → reword/reorder only | `enhanced` → infer adjacent skills the experience clearly implies, frame experience strongly | `aggressive` → full overhaul, freely adds tools/skills not in profile to make the candidate the ideal fit. **No level may invent employers, titles, dates, or fabricate numeric metrics.** Anything added/inferred must be marked `inferred=true` and surfaced in the review panel before export.

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
