"""External interview-data discovery for phase 2b.

Best-effort only: if no reliable public data is found, callers should fall back
to AI-generated interview prep.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .humanize import clean_text
from .models import InterviewPrepData, InterviewPrepReference, InterviewQuestion

MAX_RESULTS = 5
MAX_PAGE_FETCH = 3
MAX_QUESTIONS = 7

UA = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
	"AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/126.0.0.0 Safari/537.36"
)


def _now() -> str:
	return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _search_query(job: dict[str, Any]) -> str:
	company = (job.get("company") or "").strip()
	title = (job.get("title") or "").strip()
	if company and title:
		return f"{company} {title} interview questions experience"
	if company:
		return f"{company} interview questions experience"
	if title:
		return f"{title} interview questions"
	return "job interview questions experience"


def _extract_questions(text: str) -> list[str]:
	out: list[str] = []
	seen: set[str] = set()
	for chunk in re.split(r"\n+|(?<=[?])\s+", text):
		candidate = clean_text(chunk.strip(" -•\t"))
		if not candidate.endswith("?"):
			continue
		if len(candidate) < 20 or len(candidate) > 220:
			continue
		lower = candidate.lower()
		if lower in seen:
			continue
		seen.add(lower)
		out.append(candidate)
		if len(out) >= MAX_QUESTIONS:
			break
	return out


def _focus_areas(questions: list[str]) -> list[str]:
	buckets = {
		"System design": ("design", "architecture", "scal", "distributed", "microservice"),
		"Coding": ("code", "algorithm", "complexity", "python", "javascript", "sql"),
		"Behavioural": ("conflict", "team", "challenge", "stakeholder", "communication"),
		"Role motivation": ("why", "company", "role", "interested"),
		"Delivery impact": ("impact", "deadline", "priority", "trade-off"),
	}
	text = " ".join(q.lower() for q in questions)
	found: list[str] = []
	for label, keywords in buckets.items():
		if any(k in text for k in keywords):
			found.append(label)
	return found[:4]


def fetch_external_interview_prep(job: dict[str, Any]) -> InterviewPrepData | None:
	"""Return sourced interview prep from public web snippets/pages, or None."""
	query = _search_query(job)
	headers = {"User-Agent": UA}

	with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
		search_resp = client.get("https://duckduckgo.com/html/", params={"q": query})
		if search_resp.status_code != 200:
			return None

		soup = BeautifulSoup(search_resp.text, "html.parser")
		nodes = soup.select("a.result__a")[:MAX_RESULTS]
		refs: list[InterviewPrepReference] = []

		for node in nodes:
			href = (node.get("href") or "").strip()
			title = clean_text(node.get_text(" ", strip=True))
			if not href or not title:
				continue
			snippet_node = node.find_parent("div", class_="result")
			snippet = ""
			if snippet_node:
				s = snippet_node.select_one("a.result__snippet") or snippet_node.select_one(
					".result__snippet"
				)
				if s:
					snippet = clean_text(s.get_text(" ", strip=True))
			refs.append(InterviewPrepReference(title=title, url=href, snippet=snippet))

		if not refs:
			return None

		question_text_chunks: list[str] = []
		for ref in refs[:MAX_PAGE_FETCH]:
			if ref.snippet:
				question_text_chunks.append(ref.snippet)
			try:
				page = client.get(ref.url)
				if page.status_code != 200:
					continue
				page_soup = BeautifulSoup(page.text, "html.parser")
				text = clean_text(page_soup.get_text(" ", strip=True))
				question_text_chunks.append(text[:18000])
			except Exception:
				continue

	candidates = _extract_questions("\n".join(question_text_chunks))
	if not candidates:
		return None

	company = (job.get("company") or "this company").strip() or "this company"
	questions: list[InterviewQuestion] = []
	for item in candidates[:MAX_QUESTIONS]:
		host = ""
		if refs:
			host = urlparse(refs[0].url).netloc.replace("www.", "")
		why = f"Seen in public interview discussions for {company}"
		if host:
			why += f" (source: {host})"
		questions.append(
			InterviewQuestion(
				question=item,
				why_relevant=why,
				difficulty="medium",
			)
		)

	return InterviewPrepData(
		questions=questions,
		tips=(
			"External interview notes are crowd-sourced and can vary by role and region. "
			"Use these as prep prompts, then verify against the current job description."
		),
		focus_areas=_focus_areas(candidates),
		references=refs,
		source_note=(
			"External data enabled: sourced from public web results and may include user-generated content."
		),
		generated_at=_now(),
		source="external",
	)
