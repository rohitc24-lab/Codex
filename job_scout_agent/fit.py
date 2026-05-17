"""Resume-to-job fit scoring utilities."""

from __future__ import annotations

import re
from collections import Counter

from .models import JobFit

STOP_WORDS = {
    "about", "after", "also", "and", "are", "but", "can", "for", "from", "has",
    "have", "into", "job", "our", "the", "this", "that", "with", "will", "you", "your",
    "role", "work", "team", "using", "years", "experience", "skills", "remote", "india",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#]*(?:[.\-][a-zA-Z0-9+#]+)*", text)]


def important_keywords(text: str, *, limit: int = 24) -> tuple[str, ...]:
    tokens = [token for token in tokenize(text) if token not in STOP_WORDS and len(token) > 2]
    counts = Counter(tokens)
    return tuple(keyword for keyword, _ in counts.most_common(limit))


def score_fit(resume_text: str, job_description: str) -> JobFit:
    """Score a resume against a job description using transparent keyword overlap.

    This deterministic scorer is intentionally simple so an ATS analyzer agent can later
    replace or augment it without changing the search workflow.
    """

    job_keywords = important_keywords(job_description)
    resume_keywords = set(important_keywords(resume_text, limit=80))
    if not job_keywords:
        return JobFit(0, (), (), "No job-description keywords were available to compare.")

    matched = tuple(keyword for keyword in job_keywords if keyword in resume_keywords)
    missing = tuple(keyword for keyword in job_keywords if keyword not in resume_keywords)[:10]
    score = round((len(matched) / len(job_keywords)) * 100)
    if score >= 75:
        rationale = "Strong fit based on resume keyword coverage of the job description."
    elif score >= 45:
        rationale = "Moderate fit; tailor the resume around the missing job keywords."
    else:
        rationale = "Low fit from keyword coverage; review the missing skills before applying."
    return JobFit(score, matched, missing, rationale)
