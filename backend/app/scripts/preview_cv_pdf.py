"""Generate an adversarial CV PDF fixture for renderer validation.

Run:
    uv run python -m app.scripts.preview_cv_pdf
    uv run python -m app.scripts.preview_cv_pdf data/preview-base14.pdf base14
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pypdf import PdfReader

from ..config import DATA_DIR
from ..models import CVBullet, CVEducation, CVExperience, CVProject, GeneratedCV

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger(__name__)


def _fixture_cv() -> GeneratedCV:
    long_bullet = (
        "Built a resilient ingestion pipeline that captured, normalized, deduplicated, "
        "scored, and routed high-volume vacancy updates across source adapters with "
        "strict idempotency guarantees and replay tooling, reducing time-to-shortlist "
        "while preserving auditability for every transformation under rolling deployment."
    )

    return GeneratedCV(
        full_name="Ren\u00e9e \u00d3 S\u00failleabh\u00e1in",
        headline="Senior Platform Engineer for Data and AI Hiring Systems",
        contact=[
            "renee@example.com",
            "+353 87 000 0000",
            "Dublin, Ireland",
            "https://www.linkedin.com/in/renee-o-suilleabhain-profile-with-an-extraordinarily-long-url",
            "https://github.com/renee-platform",
            "https://renee.dev",
        ],
        summary=(
            "Platform engineer focused on high-volume recruitment systems and reliable developer tooling. "
            "Scaled ingestion to 40k jobs/day (<10ms p99) for R&D & platform teams while hardening "
            "production observability and release safety with na\u00efve assumptions removed and target comp at \u20ac180k."
        ),
        skills=[
            "Python",
            "FastAPI",
            "TypeScript",
            "React",
            "SQLite",
            "PostgreSQL",
            "Redis",
            "Kafka",
            "OpenTelemetry",
            "Prometheus",
            "Grafana",
            "Docker",
            "Kubernetes",
            "AWS",
            "CI/CD",
            "Feature flags",
            "A/B testing",
            "Prompt engineering",
            "Model evaluation",
            "Data contracts",
            "Schema evolution",
            "Incident response",
        ],
        experience=[
            CVExperience(
                role="Principal Platform Engineer, JobMatch Systems International",
                company="Acme Digital Hiring",
                dates="September 2019 - Present (contract)",
                location="Dublin, Ireland",
                bullets=[
                    CVBullet(text=long_bullet),
                    CVBullet(text="Scaled ingestion to 40k jobs/day (<10ms p99) for R&D & platform teams."),
                    CVBullet(text="Built event lineage from source \u2192 transform \u2192 rank with availability \u226599.9% across the critical path."),
                    CVBullet(text="Raised matching precision to >=99.9% on canonical dedup keys while lowering storage cost by 22% year-over-year."),
                    CVBullet(text="Drove weekly releases with automated rollback and documented runbooks for 24/7 ownership."),
                    CVBullet(text="Partnered with legal and security on privacy controls for candidate and employer data."),
                    CVBullet(text="Mentored five engineers and introduced review standards that reduced regressions by 38%."),
                ],
            ),
            CVExperience(
                role="Senior Engineer",
                company="Northlight Labs",
                dates="Mar 2017 - Aug 2019",
                location="",
                bullets=[
                    CVBullet(text="Implemented vacancy parsing and enrichment services that cut manual triage effort by 60%."),
                    CVBullet(text="Built role-specific ranking models and monitoring, improving shortlist acceptance from 31% to 47%."),
                    CVBullet(text="Introduced contract tests for upstream feeds and eliminated repeated integration outages."),
                    CVBullet(text="Coordinated incident reviews and delivered remediation within agreed SLA windows."),
                    CVBullet(text="Maintained internal documentation used by support, operations, and engineering teams."),
                ],
            ),
            CVExperience(
                role="Software Engineer",
                company="Metrics Foundry",
                dates="",
                location="Galway, Ireland",
                bullets=[
                    CVBullet(text="Developed APIs for analytics ingest and reporting used across three product lines."),
                    CVBullet(text="Improved query plans and caching to stabilize p95 latency under peak traffic."),
                    CVBullet(text="Collaborated with product managers to prioritize reliability work alongside features."),
                    CVBullet(text="Owned deployment automation and operational handover for new services."),
                    CVBullet(text="Contributed to hiring loops and onboarding materials for new team members."),
                ],
            ),
            CVExperience(
                role="Graduate Developer",
                company="City Labs",
                dates="Jul 2015 - Feb 2017",
                location="Limerick, Ireland",
                bullets=[
                    CVBullet(text="Shipped dashboard components and backend endpoints for weekly customer reporting."),
                    CVBullet(text="Supported production issues and learned incident response fundamentals."),
                    CVBullet(text="Maintained integration scripts and documentation for partner onboarding."),
                    CVBullet(text="Helped migrate legacy jobs to containerized workloads."),
                    CVBullet(text="Assisted with test automation and release checklists."),
                ],
            ),
        ],
        projects=[
            CVProject(
                name="Matching Intelligence Platform",
                technologies=["Python", "FastAPI", "PostgreSQL", "Redis", "OpenTelemetry", "Grafana", "Docker", "AWS"],
                description="Designed and delivered an evidence-based matching service with traceable feature contributions and human review controls.",
            ),
            CVProject(
                name="Vacancy Signals Workbench",
                technologies=["TypeScript", "React", "Vite"],
                description="Built a reviewer-facing interface that accelerated screening decisions without sacrificing auditability.",
            ),
        ],
        education=[
            CVEducation(qualification="BSc Computer Science", institution="University of Limerick", year="2015"),
            CVEducation(qualification="Higher Certificate in Data Analytics", institution="Atlantic Technological University", year="2013"),
        ],
    )


def _report_pdf(path: Path) -> None:
    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    print(f"pages: {page_count}")

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        print(f"page {i} extracted chars: {len(text)}")

    if reader.pages:
        sample = (reader.pages[0].extract_text() or "").strip()
        print("\n--- page 1 extracted text ---")
        print(sample)


def main() -> int:
    out_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else (DATA_DIR / "preview-cv.pdf")
    mode = (sys.argv[2].strip().lower() if len(sys.argv) > 2 else "embedded")
    if mode not in {"embedded", "base14"}:
        print("mode must be 'embedded' or 'base14'")
        return 1

    out_path = out_arg if out_arg.is_absolute() else (Path.cwd() / out_arg)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["JOBMATCH_PDF_FONTS"] = mode

    # Import after env selection so this run is deterministic.
    from ..cv_pdf import _register_fonts, render_cv_pdf

    body, heading = _register_fonts(mode)
    print(f"font mode={mode} body={body} heading={heading}")

    cv = _fixture_cv()
    render_cv_pdf(cv, out_path)
    print(f"rendered: {out_path}")

    _report_pdf(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
