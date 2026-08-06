"""Deterministic CV PDF renderer.

This module owns CV PDF layout and typography. See documents.py for ATS layout
rules that both DOCX and PDF outputs follow.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from html import escape
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.fonts import tt2ps
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.lib.styles import ParagraphStyle

from .models import CVEducation, CVExperience, CVProject, GeneratedCV

log = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

PDF_MARGIN_X = 54
PDF_MARGIN_TOP = 44
PDF_MARGIN_BOT = 48

PDF_INK = HexColor("#1A1A1A")
PDF_HEAD = HexColor("#1F2A37")
PDF_MUTED = HexColor("#555F6D")
PDF_RULE = HexColor("#9AA3AF")

PDF_RULE_WIDTH = 0.6

SP_AFTER_CONTACT = 15
SECTION_SP_BEFORE = 13
SECTION_RULE_GAP = 3.5
SECTION_SP_AFTER = 7
ENTRY_SP_BEFORE = 9
META_SP_AFTER = 3
BODY_SP_AFTER = 4
BULLET_SP_AFTER = 2.5
SECTION_MIN = 62

BULLET_CHAR = "\u2022"
BULLET_INDENT = 2
BULLET_LEFT = 13

_WINANSI_FIXUPS = {
    "\u2192": "->",
    "\u2190": "<-",
    "\u21d2": "=>",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2260": "!=",
    "\u00d7": "x",
    "\u2011": "-",
    "\u2212": "-",
    "\u00a0": " ",
    "\u2713": "-",
    "\u25aa": "-",
}


def _font_mode() -> str:
    mode = os.getenv("JOBMATCH_PDF_FONTS", "embedded").strip().lower()
    return "base14" if mode == "base14" else "embedded"


@lru_cache(maxsize=2)
def _register_fonts(mode: str) -> tuple[str, str]:
    """Return (body_family, heading_family) and register TTFs when enabled."""
    if mode == "base14":
        return ("Times-Roman", "Helvetica")

    body_family = "SourceSerif4"
    heading_family = "SourceSans3"

    face_specs = [
        (body_family, "", FONTS_DIR / "SourceSerif4-Regular.ttf"),
        (body_family, "-Bold", FONTS_DIR / "SourceSerif4-Semibold.ttf"),
        (body_family, "-Italic", FONTS_DIR / "SourceSerif4-It.ttf"),
        (body_family, "-BoldItalic", FONTS_DIR / "SourceSerif4-Semibold.ttf"),
        (heading_family, "", FONTS_DIR / "SourceSans3-Regular.ttf"),
        (heading_family, "-Bold", FONTS_DIR / "SourceSans3-Semibold.ttf"),
        (heading_family, "-Italic", FONTS_DIR / "SourceSans3-It.ttf"),
        (heading_family, "-BoldItalic", FONTS_DIR / "SourceSans3-Semibold.ttf"),
    ]

    try:
        for family, suffix, path in face_specs:
            if not path.exists():
                raise FileNotFoundError(f"Missing font file: {path}")
            name = f"{family}{suffix}"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))

        pdfmetrics.registerFontFamily(
            body_family,
            normal=body_family,
            bold=f"{body_family}-Bold",
            italic=f"{body_family}-Italic",
            boldItalic=f"{body_family}-BoldItalic",
        )
        pdfmetrics.registerFontFamily(
            heading_family,
            normal=heading_family,
            bold=f"{heading_family}-Bold",
            italic=f"{heading_family}-Italic",
            boldItalic=f"{heading_family}-BoldItalic",
        )
        return (body_family, heading_family)
    except Exception as exc:  # noqa: BLE001 - degrade safely
        log.warning("Embedded fonts unavailable; falling back to base-14: %s", exc)
        return ("Times-Roman", "Helvetica")


def _using_base14() -> bool:
    body, heading = _register_fonts(_font_mode())
    return body == "Times-Roman" and heading == "Helvetica"


def _pdf_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if _using_base14():
        for src, dst in _WINANSI_FIXUPS.items():
            text = text.replace(src, dst)
        text = text.encode("cp1252", "replace").decode("cp1252")
    return text


def _esc(value: str | None) -> str:
    return escape(_pdf_text(value))


class SectionHeading(Flowable):
    def __init__(self, text: str, style: ParagraphStyle):
        super().__init__()
        self.text = _pdf_text(text).upper()
        self.style = style
        self._width = 0.0

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self._width = avail_width
        height = self.style.fontSize + SECTION_RULE_GAP + PDF_RULE_WIDTH
        return avail_width, height

    def draw(self) -> None:
        c = self.canv
        c.setFont(self.style.fontName, self.style.fontSize)
        c.setFillColor(self.style.textColor)
        c.drawString(
            0,
            SECTION_RULE_GAP + PDF_RULE_WIDTH,
            self.text,
            charSpace=0.95,
        )
        c.setStrokeColor(PDF_RULE)
        c.setLineWidth(PDF_RULE_WIDTH)
        c.setLineCap(0)
        c.line(0, 0, self._width, 0)


@lru_cache(maxsize=2)
def _styles(mode: str) -> tuple[dict[str, ParagraphStyle], dict[str, str]]:
    body, heading = _register_fonts(mode)

    faces = {
        "reg": heading,
        "bold": tt2ps(heading, 1, 0),
        "ital": tt2ps(heading, 0, 1),
        "sans_reg": heading,
        "sans_bold": tt2ps(heading, 1, 0),
        "sans_ital": tt2ps(heading, 0, 1),
    }

    common = dict(
        allowWidows=0,
        allowOrphans=0,
        splitLongWords=False,
    )

    styles = {
        "name": ParagraphStyle(
            "cv_name",
            fontName=faces["sans_bold"],
            fontSize=20,
            leading=23,
            alignment=1,
            textColor=PDF_HEAD,
            spaceAfter=2,
        ),
        "headline": ParagraphStyle(
            "cv_headline",
            fontName=faces["sans_reg"],
            fontSize=11,
            leading=13.5,
            alignment=1,
            textColor=PDF_MUTED,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "cv_contact",
            fontName=faces["sans_reg"],
            fontSize=9,
            leading=11.5,
            alignment=1,
            textColor=PDF_MUTED,
            spaceAfter=SP_AFTER_CONTACT,
        ),
        "section": ParagraphStyle(
            "cv_section",
            fontName=faces["sans_bold"],
            fontSize=9.5,
            leading=9.5,
            textColor=HexColor("#334155"),
        ),
        "body": ParagraphStyle(
            "cv_body",
            fontName=faces["reg"],
            fontSize=10.5,
            leading=13.6,
            textColor=PDF_INK,
            spaceAfter=BODY_SP_AFTER,
            **common,
        ),
        "role": ParagraphStyle(
            "cv_role",
            fontName=faces["bold"],
            fontSize=11,
            leading=13.6,
            textColor=PDF_HEAD,
            **common,
        ),
        "roleline": ParagraphStyle(
            "cv_roleline",
            fontName=faces["reg"],
            fontSize=10.5,
            leading=12.8,
            textColor=PDF_HEAD,
            **common,
        ),
        "meta": ParagraphStyle(
            "cv_meta",
            fontName=faces["sans_ital"],
            fontSize=9,
            leading=11.5,
            textColor=PDF_MUTED,
            spaceAfter=META_SP_AFTER,
            **common,
        ),
        "bullet": ParagraphStyle(
            "cv_bullet",
            fontName=faces["reg"],
            fontSize=10.5,
            leading=13.6,
            textColor=PDF_INK,
            leftIndent=BULLET_LEFT,
            bulletIndent=BULLET_INDENT,
            bulletFontName=faces["reg"],
            spaceAfter=BULLET_SP_AFTER,
            **common,
        ),
        "footer": ParagraphStyle(
            "cv_footer",
            fontName=faces["sans_reg"],
            fontSize=8,
            leading=9.5,
            textColor=PDF_MUTED,
        ),
    }
    return styles, faces


def _section(title: str, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    return [
        Spacer(1, SECTION_SP_BEFORE),
        CondPageBreak(SECTION_MIN),
        SectionHeading(title, styles["section"]),
        Spacer(1, SECTION_SP_AFTER),
    ]


def _experience_block(
    exp: CVExperience,
    styles: dict[str, ParagraphStyle],
    faces: dict[str, str],
) -> list[Flowable]:
    flowables: list[Flowable] = [Spacer(1, ENTRY_SP_BEFORE)]
    role_line = ""
    if exp.role:
        role_line = f"<b>{_esc(exp.role)}</b>"
    if exp.company:
        role_line += f'<font color="#555F6D">, {_esc(exp.company)}</font>'
    if role_line:
        flowables.append(Paragraph(role_line, styles["roleline"]))

    meta_bits = [bit for bit in (_pdf_text(exp.dates), _pdf_text(exp.location)) if bit]
    if meta_bits:
        flowables.append(Paragraph(_esc("  |  ".join(meta_bits)), styles["meta"]))

    bullets = [
        Paragraph(_esc(bullet.text), styles["bullet"], bulletText=BULLET_CHAR)
        for bullet in exp.bullets
        if _pdf_text(bullet.text)
    ]

    if bullets and role_line:
        flowables.append(KeepTogether(bullets[:2]))
        flowables.extend(bullets[2:])
    else:
        flowables.extend(bullets)

    return flowables


def _project_block(proj: CVProject, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    flowables: list[Flowable] = [Spacer(1, 6)]
    title = f"<b>{_esc(proj.name)}</b>" if proj.name else "<b>Project</b>"
    if proj.technologies:
        tech = _esc(", ".join(t for t in proj.technologies if _pdf_text(t)))
        if tech:
            title += f'  <font size="9" color="#555F6D">({tech})</font>'
    flowables.append(Paragraph(title, styles["body"]))
    if proj.description:
        flowables.append(Paragraph(_esc(proj.description), styles["body"]))
    return flowables


def _education_block(
    edu: CVEducation,
    styles: dict[str, ParagraphStyle],
    faces: dict[str, str],
) -> list[Flowable]:
    line = ""
    if edu.qualification:
        line = f"<b>{_esc(edu.qualification)}</b>"
    tail = ", ".join(part for part in (_pdf_text(edu.institution), _pdf_text(edu.year)) if part)
    if tail:
        line += f", {_esc(tail)}" if line else _esc(tail)
    if not line:
        return []
    return [Paragraph(line, styles["body"])]


def _story(cv: GeneratedCV, styles: dict[str, ParagraphStyle], faces: dict[str, str]) -> list[Flowable]:
    story: list[Flowable] = []

    name = _pdf_text(cv.full_name)
    if name:
        story.append(Paragraph(_esc(name), styles["name"]))

    if cv.headline:
        story.append(Paragraph(_esc(cv.headline), styles["headline"]))

    if cv.contact:
        contact = "  |  ".join(_esc(item) for item in cv.contact if _pdf_text(item))
        if contact:
            story.append(Paragraph(contact, styles["contact"]))

    if cv.summary:
        story.extend(_section("Professional Summary", styles))
        story.append(Paragraph(_esc(cv.summary), styles["body"]))

    if cv.skills:
        skills = ", ".join(_pdf_text(skill) for skill in cv.skills if _pdf_text(skill))
        if skills:
            story.extend(_section("Skills", styles))
            story.append(Paragraph(_esc(skills), styles["body"]))

    if cv.experience:
        story.extend(_section("Experience", styles))
        for exp in cv.experience:
            story.extend(_experience_block(exp, styles, faces))

    if cv.projects:
        story.extend(_section("Projects", styles))
        for proj in cv.projects:
            story.extend(_project_block(proj, styles))

    if cv.education:
        story.extend(_section("Education", styles))
        for edu in cv.education:
            story.extend(_education_block(edu, styles, faces))

    if not story:
        story.append(Spacer(1, 1))

    return story


def render_cv_pdf(cv: GeneratedCV, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    mode = _font_mode()
    styles, faces = _styles(mode)

    candidate_name = _pdf_text(cv.full_name) or "Candidate"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=PDF_MARGIN_X,
        rightMargin=PDF_MARGIN_X,
        topMargin=PDF_MARGIN_TOP,
        bottomMargin=PDF_MARGIN_BOT,
        title=f"{candidate_name} - CV",
        author=candidate_name,
        subject="Curriculum Vitae",
        creator="JobMatch",
    )

    story = _story(cv, styles, faces)
    doc.build(story)
    return path
