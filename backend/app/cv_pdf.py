"""Deterministic CV PDF renderer.

This module owns CV PDF layout and typography. See documents.py for ATS layout
rules that both DOCX and PDF outputs follow.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache, partial
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
PDF_FOOTER_Y = 26

PDF_INK = HexColor("#1A1A1A")
PDF_HEAD = HexColor("#1F2A37")
PDF_MUTED = HexColor("#555F6D")
PDF_RULE = HexColor("#9AA3AF")

PDF_SECTION_TRACK = 0.95
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

PDF_LR_GAP = 12
PDF_LR_MIN_LEFT_RATIO = 0.45
PDF_LR_DESCENDER = 0.21

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


def _flatten_run_words(runs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for text, font in runs:
        for word in _pdf_text(text).split():
            if word in {",", ";", ":"} and out:
                prev_word, prev_font = out[-1]
                out[-1] = (prev_word + word, prev_font)
                continue
            out.append((word, font))
    return out


def _wrap_runs(
    runs: list[tuple[str, str]],
    first_width: float,
    rest_width: float,
    size: float,
) -> list[list[tuple[str, str]]]:
    words = _flatten_run_words(runs)
    if not words:
        return []

    lines: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    line_index = 0
    current_width = 0.0

    for word, font in words:
        word_w = pdfmetrics.stringWidth(word, font, size)
        space_w = pdfmetrics.stringWidth(" ", font, size) if current else 0.0
        limit = first_width if line_index == 0 else rest_width

        if current and (current_width + space_w + word_w) > max(limit, 1.0):
            lines.append(current)
            current = [(word, font)]
            line_index += 1
            current_width = word_w
            continue

        current.append((word, font))
        current_width += space_w + word_w

    if current:
        lines.append(current)
    return lines


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
            charSpace=PDF_SECTION_TRACK,
        )
        c.setStrokeColor(PDF_RULE)
        c.setLineWidth(PDF_RULE_WIDTH)
        c.setLineCap(0)
        c.line(0, 0, self._width, 0)


class LeftRightLine(Flowable):
    def __init__(
        self,
        runs: list[tuple[str, str]],
        right: str,
        *,
        left_size: float,
        left_leading: float,
        right_font: str,
        right_size: float,
        right_color,
    ):
        super().__init__()
        self.runs = runs
        self.right = _pdf_text(right)
        self.left_size = left_size
        self.left_leading = left_leading
        self.right_font = right_font
        self.right_size = right_size
        self.right_color = right_color
        self._width = 0.0
        self._height = 0.0
        self._stacked = False
        self._lines: list[list[tuple[str, str]]] = []

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self._width = avail_width
        right_w = (
            pdfmetrics.stringWidth(self.right, self.right_font, self.right_size)
            if self.right
            else 0.0
        )

        left_first = avail_width - right_w - PDF_LR_GAP if self.right else avail_width
        self._stacked = bool(self.right and left_first < (avail_width * PDF_LR_MIN_LEFT_RATIO))

        if self._stacked:
            self._lines = _wrap_runs(self.runs, avail_width, avail_width, self.left_size)
        else:
            self._lines = _wrap_runs(self.runs, left_first, avail_width, self.left_size)

        left_lines = max(1, len(self._lines))
        left_h = left_lines * self.left_leading
        right_h = self.right_size * 1.2 if (self._stacked and self.right) else 0.0
        self._height = left_h + right_h
        return avail_width, self._height

    def _draw_left_line(self, y: float, line: list[tuple[str, str]]) -> None:
        c = self.canv
        fragments: list[tuple[str, str]] = []
        for i, (word, font) in enumerate(line):
            text = word if i == 0 else f" {word}"
            if fragments and fragments[-1][1] == font:
                prev_text, prev_font = fragments[-1]
                fragments[-1] = (prev_text + text, prev_font)
            else:
                fragments.append((text, font))

        x = 0.0
        c.setFillColor(PDF_HEAD)
        for text, font in fragments:
            c.setFont(font, self.left_size)
            c.drawString(x, y, text)
            x += pdfmetrics.stringWidth(text, font, self.left_size)

    def draw(self) -> None:
        c = self.canv
        baseline = self._height - self.left_size + (self.left_size * PDF_LR_DESCENDER)

        for line in self._lines:
            self._draw_left_line(baseline, line)
            baseline -= self.left_leading

        if self.right:
            c.setFont(self.right_font, self.right_size)
            c.setFillColor(self.right_color)
            right_y = (
                self._height - self.right_size + (self.right_size * PDF_LR_DESCENDER)
                if self._stacked
                else self._height - self.left_size + (self.left_size * PDF_LR_DESCENDER)
            )
            c.drawRightString(self._width, right_y, self.right)


@lru_cache(maxsize=2)
def _styles(mode: str) -> tuple[dict[str, ParagraphStyle], dict[str, str]]:
    body, heading = _register_fonts(mode)

    faces = {
        "reg": body,
        "bold": tt2ps(body, 1, 0),
        "ital": tt2ps(body, 0, 1),
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
            textColor=PDF_HEAD,
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
    lead: list[Flowable] = []

    runs: list[tuple[str, str]] = []
    if exp.role:
        runs.append((_pdf_text(exp.role), faces["bold"]))
    if exp.company:
        prefix = ", " if runs else ""
        runs.append((f"{prefix}{_pdf_text(exp.company)}", faces["reg"]))

    if runs or exp.dates:
        lead.append(
            LeftRightLine(
                runs=runs,
                right=exp.dates,
                left_size=11,
                left_leading=13.6,
                right_font=faces["sans_reg"],
                right_size=9,
                right_color=PDF_MUTED,
            )
        )

    if exp.location:
        lead.append(Paragraph(_esc(exp.location), styles["meta"]))

    bullets = [
        Paragraph(_esc(bullet.text), styles["bullet"], bulletText=BULLET_CHAR)
        for bullet in exp.bullets
        if _pdf_text(bullet.text)
    ]

    if bullets and lead:
        flowables.append(KeepTogether([*lead, *bullets[:2]]))
        flowables.extend(bullets[2:])
    else:
        flowables.extend(lead)
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
    runs: list[tuple[str, str]] = []
    if edu.qualification:
        runs.append((_pdf_text(edu.qualification), faces["bold"]))
    if edu.institution:
        prefix = ", " if runs else ""
        runs.append((f"{prefix}{_pdf_text(edu.institution)}", faces["reg"]))

    return [
        LeftRightLine(
            runs=runs,
            right=edu.year,
            left_size=10.5,
            left_leading=13.6,
            right_font=faces["sans_reg"],
            right_size=9,
            right_color=PDF_MUTED,
        )
    ]


def _draw_cv_footer(canv, doc, *, name: str, styles: dict[str, ParagraphStyle]) -> None:
    footer = styles["footer"]
    y = PDF_FOOTER_Y
    canv.setFont(footer.fontName, footer.fontSize)
    canv.setFillColor(footer.textColor)
    canv.drawString(PDF_MARGIN_X, y, _pdf_text(name))
    canv.drawRightString(doc.width + doc.leftMargin, y, f"Page {canv.getPageNumber()}")


def _story(cv: GeneratedCV, styles: dict[str, ParagraphStyle], faces: dict[str, str]) -> list[Flowable]:
    story: list[Flowable] = []

    name = _pdf_text(cv.full_name)
    if name:
        story.append(Paragraph(_esc(name), styles["name"]))

    if cv.headline:
        story.append(Paragraph(_esc(cv.headline), styles["headline"]))

    if cv.contact:
        contact = " \u00b7 ".join(_esc(item) for item in cv.contact if _pdf_text(item))
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
    on_later = partial(_draw_cv_footer, name=candidate_name, styles=styles)
    doc.build(story, onLaterPages=on_later)
    return path
