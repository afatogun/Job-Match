# JobMatch Local

A single-user local app for discovering genuine job vacancies in Ireland and (later)
generating tailored CVs and cover letters.

**Current status — development steps 1–6 complete.** Job discovery works end to end
against Indeed Ireland. Profile parsing, AI ranking and document generation are not built yet.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python for you)
- Node.js 20+

> The backend pins **Python 3.12**. This is not cosmetic: `python-jobspy` hard-pins
> `numpy==1.26.3`, whose Windows wheels stop at cp312, so it cannot install on 3.13+.
> `uv` reads `backend/.python-version` and fetches 3.12 automatically.

## Setup

```powershell
cd backend
uv sync

cd ..\frontend
npm install
```

## Run

```powershell
.\dev.ps1
```

Or in two terminals:

```powershell
cd backend;  uv run uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev
```

Then open **http://localhost:5173**. The API is at http://127.0.0.1:8000 with
interactive docs at `/docs`.

## Using it

1. **Settings** — set your target job titles, location (default `Ireland`), maximum job
   age, and work arrangement. Save.
2. **Jobs** — press **Find New Jobs**. Each target title is searched against every enabled
   source; progress is shown live.
3. Click a job to read the full description, or **Open Original Job** to go straight to the
   genuine posting on the source site.
4. Set a status on any job (New / Saved / Generated / Applied / Interview / Rejected).

Every job links to its real posting. Nothing is synthesised.

## Verify it is returning genuine data

```powershell
cd backend
uv run python -m app.scripts.smoke_indeed
uv run python -m app.scripts.smoke_indeed "Backend Engineer"
```

This calls the scraper directly and prints live listings with their URLs, independent of
the app. If it returns nothing, try setting the location to `Dublin, Ireland` in Settings.

## Layout

```
backend/app/
  sources/       one module per job board; registry.py is the extension point
  pipeline.py    collect -> normalise -> filter -> dedup -> store
  normalise.py   NaN/date/location cleanup, dedup keys
  routers/       HTTP layer
frontend/src/
  pages/         Jobs, Job detail, Settings (+ Profile/Applications placeholders)
data/            jobmatch.db, uploads/, generated/   (gitignored)
```

### Adding a job source

Write a module in `backend/app/sources/` exposing `fetch(settings, search_term) -> SourceResult`,
then add one line to `SOURCES` in `registry.py`. The pipeline needs no changes. A source that
raises or rate-limits is recorded and skipped — it never stops the other sources.

## Notes and limitations

- **Deduplication** keys on source job ID, then canonical URL, then company+title+location.
  Re-running a search updates existing rows rather than duplicating them.
- **Work arrangement**: job boards only expose a remote flag. `remote` is filtered at the
  source; `hybrid` and `on-site` are approximated from the listing text and are imprecise.
- **Match scores** are intentionally blank. They arrive with local scoring (step 10) and AI
  ranking (step 13); showing a placeholder number would be misleading.
- **OpenAI key** can be saved in Settings (written to `.env`) but nothing calls it yet.
- **Salaries are usually absent** — most Irish Indeed listings simply don't state one.
- **Indeed blocks `curl`** with a 403, so don't test job links from the command line; they
  open normally in a browser. Direct employer links (Workday, Greenhouse, Ashby, …) resolve fine.
- **Indeed's own results occasionally include a non-Irish role.** Listings are stored exactly
  as the source returned them rather than second-guessed; the location and the direct link
  make such outliers obvious.

## Not built yet

Steps 7–20: Glassdoor, JobsIreland, relevance scoring, profile upload, AI ranking,
augmentation levels, CV and cover-letter generation, DOCX/PDF export, bulk generation, LinkedIn.
