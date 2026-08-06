# JobMatch Local

A single-user local app for discovering genuine job vacancies in Ireland and generating
tailored CVs and cover letters for the ones worth applying to.

**Status - all 20 development steps built.** Job discovery, local + AI ranking, profile
extraction, augmentation-controlled CV and cover-letter generation, DOCX/PDF export,
statuses and bulk generation all work end to end.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python for you)
- Node.js 20+
- An OpenAI API key (only for profile parsing, ranking and generation - job discovery works without one)
- Microsoft Word **or** LibreOffice, for PDF export. Without either you still get DOCX.

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

Put your key in `.env` at the repo root (copy `.env.example`), or paste it into Settings
in the app, which writes the same file. `.env` is gitignored; **never** put a real key in
`.env.example`, which is tracked.

## Run

```powershell
.\dev.ps1
```

Or in two terminals:

```powershell
cd backend;  uv run uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev
```

Open **http://localhost:5173**. API docs at http://127.0.0.1:8000/docs.

## Using it

1. **Profile** - upload your master CV (PDF, DOCX or TXT). Text is extracted locally, then
   structured by OpenAI. **Review and correct it.** Everything generated later is built
   from this, so errors here propagate. Add anything your CV omits under Extras - especially
   real metrics, which are what make strong CV bullets possible.
2. **Settings** - target titles, location, job age, work arrangement, excluded terms,
   model, and your default augmentation level.
3. **Jobs** - press **Find New Jobs**. Each target title is searched against every enabled
   source, scored locally, then the strongest are ranked by AI against your profile.
4. Open a job for the full description, matching skills, gaps and seniority fit.
5. Press **Generate CV & Cover Letter**, choosing an augmentation level.
6. **Applications** - preview, edit, regenerate, and download DOCX/PDF. Or select several
   jobs on the Jobs page and use **Generate Selected**.

Every job links to its real posting. Nothing is synthesised.

## Augmentation levels

Set a default in Settings; override per job at generation time.

| Level | What the model may do |
|---|---|
| **Accurate** | Only what your profile says. Rewording, reordering and re-emphasis only. |
| **Enhanced** | Rebuilds the CV around the vacancy and makes explicit the skills your real work implies. No invented systems, no new numbers, job titles untouched. |
| **Aggressive** | Closes every gap in the ad. Names initiatives and systems under your real employers, states calibrated metrics, and reframes job titles toward the role at the same seniority. |

**No level may invent an employer, change employment dates, add a degree or certification,
or add a project that is not in your profile.** Those are absolute.

Aggressive is the one that will state things you have not done, which is the point of it:
it builds the CV that gets shortlisted, using your real career as the raw material. Every
claim it makes beyond your profile is marked `inferred` on the bullet and listed in a
review panel. Read them before you export, because you will be asked about them at
interview. If you want a CV you can send without checking, use Enhanced.

Enhanced and Aggressive read the vacancy twice. The first pass extracts what the advert
actually asks for and diffs it against your profile, producing a list of what is already
evidenced and what is missing, with a specific suggestion for which real role each gap
attaches to. The CV is then written from that. One call asked to both work out what a job
demands and write a CV against it does the easy half, restating your profile in the ad's
vocabulary and calling it tailoring. The analysis is cached per job, so regenerating at a
different level does not pay for it twice.

## Writing that doesn't read as AI-written

Generated CVs and cover letters go through three layers so they don't carry the usual
machine-writing tells.

1. **Style rules in the prompt** (`HUMAN_STYLE` in `generation.py`) ban the giveaway
   vocabulary - delve, leverage, robust, seamless, spearheaded, pivotal, testament,
   "proven track record", "I am excited to", "not only ... but also" and about forty more -
   and, more importantly, target *rhythm*: vary sentence length hard, never write
   everything in threes, no participial openers, no paragraph-summarising final sentence.
   Rhythm matters more than word choice; a banned-word list is easy to satisfy while still
   sounding synthetic.
2. **A deterministic typography pass** (`humanize.py`) runs on every generated string,
   because a model will not obey "never use an em dash" across a whole document. Em and en
   dashes become commas (date ranges keep a hyphen), curly quotes become straight, ellipsis
   characters and zero-width characters are removed. The output is plain ASCII.
3. **A targeted revision pass.** Detection is deterministic, so when cliches or uniform
   sentence lengths are found, the exact problems are named back to the model in one extra
   call, with instructions to change only the flagged wording and keep every fact. Costs one
   extra call, and only when something was actually found. A revision that introduces new
   cliches or loses half the letter is rejected in favour of the original.

Anything that survives is shown as a **Writing check** panel on the application page, so you
can reword it before sending.

> **Deliberately not done:** inserting zero-width characters, homoglyphs or other tricks
> aimed at fooling AI-detection tools. Those corrupt the text layer that applicant tracking
> systems read, so they would cost real interviews to defeat a tool that is unreliable
> anyway. The goal here is writing that genuinely reads as human, not evasion.

The CV template avoids the same tells: role and company are separated by a comma rather than
an em dash, and skills are comma-separated rather than bullet-glyph separated, which also
parses more reliably for ATS keyword extraction.

## Verify it is returning genuine data

```powershell
cd backend
uv run python -m app.scripts.smoke_indeed
uv run python -m app.scripts.smoke_indeed "Backend Engineer"
uv run python -m app.scripts.smoke_indeed "AI Engineer" glassdoor
```

Calls a source directly and prints live listings with URLs, independent of the app.

## Layout

```
backend/app/
  sources/       one module per job board; registry.py is the extension point
  pipeline.py    collect -> normalise -> filter -> score -> dedup -> store -> rank
  scoring.py     cheap local relevance score, no AI
  ranking.py     batched AI ranking
  cv_import.py   PDF/DOCX -> text -> structured profile
  gap_analysis.py  reads the vacancy, diffs it against your profile
  generation.py  augmentation policy, tailored CV and cover letter
  documents.py   deterministic DOCX template + PDF conversion
frontend/src/pages/   Jobs, Job detail, Profile, Applications, Application, Settings
data/          jobmatch.db, profile.json, uploads/, generated/   (gitignored)
```

### Adding a job source

Write a module in `backend/app/sources/` exposing `fetch(settings, search_term) -> SourceResult`,
then add one line to `SOURCES` in `registry.py`. The pipeline needs no changes. A source that
raises, rate-limits or returns nothing is recorded and skipped - it never stops the others.

## Source status

Measured on 5 August 2026. All are registered and selectable in Settings.

| Source | State |
|---|---|
| **Indeed** | Working well. The default, and where the real discovery happens. |
| **Glassdoor** | Returns HTTP 400 (`location not parsed`) for every Ireland location format tried. jobspy's Glassdoor scraper appears to be blocked; off by default. |
| **JobsIreland** | Severely limited - see below. Off by default. |
| **LinkedIn** | Supported but rate-limits hard without proxies. Off by default. |

**JobsIreland limitation.** Only the ~11 most recently published vacancies are reachable
without a browser. Any query parameter (`keyWord`, `location`, `page`) makes the server
render "No jobs match this search"; pagination anchors are `Javascript:void(0)`; and
`/en-US/job-Details` returns HTTP 500 to non-browser clients, so descriptions can't be
fetched. Those few listings are mostly Community Employment schemes and general/hospitality
roles, so for software work it usually contributes nothing. Real search there would need
Playwright, which the brief asks us to avoid. The scraper is implemented and honest about
this rather than silently returning nothing.

A source failing is surfaced in the UI with its error, per search term. jobspy swallows HTTP
failures and returns an empty result, so `sources/jobspy_source.py` captures jobspy's own
error log to tell "blocked" apart from "no matches".

## Notes and limitations

- **Deduplication** keys on source job ID, then canonical URL, then company+title+location.
  Re-running a search updates existing rows rather than duplicating them.
- **Scores**: the badge shows the AI score once a job has been ranked, otherwise the local
  score, labelled so you can tell them apart. Local scoring is deterministic and free; AI
  ranking runs in batches over the top `ai_rank_top_n` jobs to avoid one call per vacancy.
- **AI ranking needs a profile.** Without one there is nothing to match against, so it is
  skipped and local scores stand.
- **Work arrangement**: job boards only expose a remote flag. `remote` is filtered at the
  source; `hybrid` and `on-site` are approximated from listing text and are imprecise.
- **Salaries are usually absent** - most Irish Indeed listings don't state one.
- **Indeed blocks `curl`** with a 403, so don't test job links from the command line; they
  open normally in a browser. Direct employer links resolve fine.
- **Indeed's own results occasionally include a non-Irish role.** Listings are stored as the
  source returned them; the location and direct link make outliers obvious.
- **Scanned PDFs won't parse** - there's no OCR. Export a text-based PDF or upload DOCX.
