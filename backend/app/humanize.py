"""Strip the tells that make generated writing read as machine-written.

Two layers:

1. Prompt rules (see generation.py) stop most of it at the source.
2. This module cleans up deterministically afterwards, because a model will not
   reliably obey "never use an em dash" across a whole document.

Deliberately NOT done here: inserting zero-width characters, homoglyphs or other
tricks aimed at fooling AI-detection tools. Those corrupt the text layer that
applicant tracking systems read, so they would cost real interviews to defeat a
tool that is unreliable anyway. Everything below produces clean, plain text.
"""

import re

# Typographic substitutions, applied in order.
_ZERO_WIDTH = re.compile(r"[​‌‍⁠﻿]")
_SPACES = re.compile(r"[    ]")
_EM_DASH = re.compile(r"\s*[—―]\s*")
_EN_DASH_RANGE = re.compile(r"(?<=\w)–(?=\w)")
_EN_DASH_OTHER = re.compile(r"\s*–\s*")
_ELLIPSIS = re.compile(r"…")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_DOUBLE_COMMA = re.compile(r",\s*,+")
_COMMA_THEN_STOP = re.compile(r",\s*([.;:])")

_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "′": "'", "″": '"',
}

# Words and phrases that read as machine-written filler. Detection only - the
# prompt does the avoiding; this is here so leftovers can be surfaced.
CLICHES = [
    "delve", "leverage", "leveraging", "utilise", "utilize", "robust", "seamless",
    "seamlessly", "spearhead", "spearheaded", "orchestrated", "pivotal", "crucial",
    "testament", "showcase", "showcasing", "underscore", "underscores", "foster",
    "facilitate", "harness", "harnessing", "empower", "empowering", "elevate",
    "unlock", "realm", "tapestry", "myriad", "plethora", "meticulous",
    "meticulously", "holistic", "cutting-edge", "state-of-the-art", "game-changer",
    "revolutionise", "revolutionize", "transformative", "synergy", "streamline",
    "streamlining", "wealth of experience", "proven track record",
    "uniquely positioned", "deep dive", "fast-paced", "it is worth noting",
    "worth noting", "not only", "i am excited", "i am thrilled", "excited to apply",
    "resonates with", "i believe i would be", "great fit", "look no further",
    "passionate about", "dynamic", "team player", "detail-oriented",
    "results-driven", "go-getter", "hit the ground running", "in today's",
    "ever-evolving", "navigate the", "at the intersection of", "i am writing to apply",
    "to whom it may concern", "at your earliest convenience", "thank you for your time and consideration",
]

_CLICHE_PATTERNS = [(c, re.compile(rf"\b{re.escape(c)}\b", re.I)) for c in CLICHES]

# Softeners. Separate from CLICHES because these are only a defect under the aggressive
# augmentation level, where the whole point is to state things outright. A model asked to
# claim something it is unsure of reaches for these rather than refusing.
HEDGES = [
    "familiar with", "exposure to", "supported work on", "assisted with",
    "gained understanding of", "gained experience in", "some experience",
    "working knowledge of", "basic understanding", "helped to", "contributed towards",
    "had the opportunity to", "was involved in", "participated in efforts",
]

_HEDGE_PATTERNS = [(h, re.compile(rf"\b{re.escape(h)}\b", re.I)) for h in HEDGES]


def clean_text(text: str | None) -> str:
    """Remove machine-writing typography. Safe to run on any generated string."""
    if not text:
        return ""

    out = _ZERO_WIDTH.sub("", text)
    out = _SPACES.sub(" ", out)

    for fancy, plain in _QUOTES.items():
        out = out.replace(fancy, plain)

    # Date and numeric ranges keep a hyphen; everything else becomes a comma,
    # which is what a spaced dash is standing in for nearly every time.
    out = _EN_DASH_RANGE.sub("-", out)
    out = _EM_DASH.sub(", ", out)
    out = _EN_DASH_OTHER.sub(", ", out)
    out = _ELLIPSIS.sub("...", out)

    # Tidy the artefacts the substitutions above can create.
    out = _DOUBLE_COMMA.sub(", ", out)
    out = _COMMA_THEN_STOP.sub(r"\1", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = _MULTI_SPACE.sub(" ", out)

    # A dash turned into a comma at the very end of a line leaves ", " dangling.
    out = re.sub(r",\s*$", "", out.strip())
    return out.strip()


def vacancy_allowed_cliches(description: str | None) -> set[str]:
    """Cliches the vacancy itself uses, which are therefore fair to reuse.

    Half of CLICHES is ordinary technical vocabulary in the right advert - robust,
    orchestrated, dynamic, streamline. HUMAN_STYLE already carves out an exception for
    words the job ad names; this is what lets the detector honour it, so a repair pass
    cannot strip a keyword the role explicitly asks for.

    Matched as substrings rather than whole words on purpose: an ad saying
    "agent orchestration" should license "orchestrated".
    """
    if not description:
        return set()
    haystack = description.lower()
    return {phrase for phrase in CLICHES if phrase in haystack}


def find_tells(*texts: str | None, allow: set[str] | None = None) -> list[str]:
    """Cliches that survived generation, so the user can see what to edit."""
    haystack = " ".join(t for t in texts if t)
    if not haystack:
        return []
    allow = allow or set()
    found = [
        phrase
        for phrase, pattern in _CLICHE_PATTERNS
        if phrase not in allow and pattern.search(haystack)
    ]
    return sorted(set(found))


def find_hedges(*texts: str | None) -> list[str]:
    """Softening language, which only counts as a defect under aggressive."""
    haystack = " ".join(t for t in texts if t)
    if not haystack:
        return []
    return sorted({phrase for phrase, pattern in _HEDGE_PATTERNS if pattern.search(haystack)})


def sentence_lengths(text: str) -> list[int]:
    return [len(s.split()) for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def reads_monotonous(text: str) -> bool:
    """Flag low burstiness - uniform sentence length is a strong machine tell."""
    lengths = sentence_lengths(text)
    if len(lengths) < 4:
        return False
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return False
    variance = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    return (variance**0.5) / mean < 0.35
