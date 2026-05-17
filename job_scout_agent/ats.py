"""ATS resume analyzer for selected job matches.

The analyzer follows the product prompt supplied for the ATS Resume Analyzer agent and
returns a structured, deterministic report that can be rendered by the UI or replaced
by an LLM-backed service later.
"""

from __future__ import annotations

import re
from textwrap import shorten
from typing import Any

from .fit import important_keywords, tokenize

ATS_SCORER_PROMPT = """You are an advanced ATS (Applicant Tracking System) optimization engine and career strategist.

Your goal is to simulate how a real ATS and hiring manager evaluate a candidate.

When a user provides a resume and job description, follow this structure strictly:

========================
STEP 1: ATS SCORE
========================
- Provide an overall ATS Match Score (0–100)
- Provide breakdown:
  - Skills Match (%)
  - Experience Relevance (%)
  - Keyword Match (%)
  - Role Alignment (%)
  - Education/Extras (%)
- Provide short justification for each

========================
STEP 2: GAP ANALYSIS
========================
- Categorize:
  1. Critical gaps (must-have)
  2. Moderate gaps
  3. Minor gaps

========================
STEP 3: KEYWORD MATCHING
========================
- Extract top 20 keywords from JD
- Show:
  - Present
  - Missing
  - Suggested additions

========================
STEP 4: RECOMMENDATIONS
========================
- Content improvements
- Bullet rewrites
- Quantification improvements
- ATS optimization tips

========================
STEP 5: COVER LETTER
========================
- Write a tailored cover letter
- Professional and concise tone

========================
STEP 6: RESUME REWRITE
========================
- Fully rewrite resume without mentioning years of experience
- ATS optimised
- Quantified impact
- Tailored to JD
- Do not fabricate experience

Always be structured, concise, and professional.
Avoid fluff."""

SKILL_TERMS = {
    "ai", "api", "apis", "automation", "aws", "azure", "ci/cd", "cloud", "docker",
    "evaluation", "fastapi", "gcp", "java", "javascript", "kubernetes", "llm", "ml",
    "observability", "python", "react", "retrieval", "sql", "typescript",
}

EDUCATION_TERMS = {
    "bachelor", "bachelors", "bs", "b.tech", "master", "masters", "ms", "mba", "phd",
    "degree", "certification", "certified", "aws", "azure", "gcp",
}

ACTION_VERBS = (
    "built", "created", "delivered", "designed", "developed", "improved", "implemented",
    "launched", "led", "managed", "optimized", "reduced", "scaled", "shipped",
)


class ATSAnalyzer:
    """Build a six-step ATS analysis from resume text and a selected job."""

    def analyze(self, resume_text: str, job: dict[str, Any]) -> dict[str, Any]:
        job_description = str(job.get("description") or job.get("job_description") or "")
        job_title = str(job.get("title") or "selected role")
        company = str(job.get("company") or "the company")
        jd_keywords = important_keywords(job_description, limit=20)
        resume_tokens = set(tokenize(resume_text))
        present = tuple(keyword for keyword in jd_keywords if keyword in resume_tokens)
        missing = tuple(keyword for keyword in jd_keywords if keyword not in resume_tokens)

        breakdown = self._score_breakdown(resume_text, job_title, jd_keywords, present, missing)
        overall = round(sum(item["score"] for item in breakdown.values()) / len(breakdown)) if breakdown else 0
        return {
            "prompt_version": "ats_scorer_v1",
            "status": "completed",
            "step_1_ats_score": {
                "overall_score": overall,
                "breakdown": breakdown,
            },
            "step_2_gap_analysis": self._gap_analysis(missing),
            "step_3_keyword_matching": {
                "top_20_keywords_from_jd": list(jd_keywords),
                "present": list(present),
                "missing": list(missing),
                "suggested_additions": self._suggested_additions(missing),
            },
            "step_4_recommendations": self._recommendations(missing, present),
            "step_5_cover_letter": self._cover_letter(resume_text, job_title, company, present),
            "step_6_resume_rewrite": self._resume_rewrite(resume_text, job_title, present, missing),
        }

    def _score_breakdown(
        self,
        resume_text: str,
        job_title: str,
        jd_keywords: tuple[str, ...],
        present: tuple[str, ...],
        missing: tuple[str, ...],
    ) -> dict[str, dict[str, Any]]:
        keyword_score = _percent(len(present), len(jd_keywords))
        skill_keywords = tuple(keyword for keyword in jd_keywords if keyword in SKILL_TERMS)
        present_skills = tuple(keyword for keyword in skill_keywords if keyword in present)
        skills_score = _percent(len(present_skills), len(skill_keywords)) if skill_keywords else keyword_score
        resume_lower = resume_text.lower()
        action_hits = sum(1 for verb in ACTION_VERBS if verb in resume_lower)
        experience_score = min(100, round((action_hits / 6) * 100)) if resume_text.strip() else 0
        role_terms = [term for term in tokenize(job_title) if len(term) > 2]
        role_hits = sum(1 for term in role_terms if term in resume_lower)
        role_score = _percent(role_hits, len(role_terms)) if role_terms else keyword_score
        education_hits = sum(1 for term in EDUCATION_TERMS if term in resume_lower)
        education_score = min(100, 40 + education_hits * 20) if education_hits else 35
        return {
            "skills_match": {
                "score": skills_score,
                "justification": f"Matched {len(present_skills)} of {len(skill_keywords) or len(jd_keywords)} skill-oriented JD terms.",
            },
            "experience_relevance": {
                "score": experience_score,
                "justification": "Based on action-oriented impact language found in the resume.",
            },
            "keyword_match": {
                "score": keyword_score,
                "justification": f"Matched {len(present)} of {len(jd_keywords)} extracted JD keywords.",
            },
            "role_alignment": {
                "score": role_score,
                "justification": f"Resume alignment with role title terms; missing keywords include {', '.join(missing[:3]) or 'none'}.",
            },
            "education_extras": {
                "score": education_score,
                "justification": "Estimated from education, certification, cloud, or extra credential terms in the resume.",
            },
        }

    def _gap_analysis(self, missing: tuple[str, ...]) -> dict[str, list[str]]:
        return {
            "critical_gaps": [f"Add credible evidence for must-have keyword: {keyword}." for keyword in missing[:5]],
            "moderate_gaps": [f"Mention relevant project context for: {keyword}." for keyword in missing[5:12]],
            "minor_gaps": [f"Consider adding this term if accurate: {keyword}." for keyword in missing[12:]],
        }

    def _suggested_additions(self, missing: tuple[str, ...]) -> list[str]:
        return [f"Include '{keyword}' only where it reflects real experience or project exposure." for keyword in missing]

    def _recommendations(self, missing: tuple[str, ...], present: tuple[str, ...]) -> dict[str, list[str]]:
        priority_terms = ", ".join(missing[:6]) or "the role's most important tools and outcomes"
        matched_terms = ", ".join(present[:6]) or "your strongest relevant skills"
        return {
            "content_improvements": [
                f"Add a targeted summary that connects {matched_terms} to the target role.",
                f"Create a skills section that honestly covers missing JD language such as {priority_terms}.",
            ],
            "bullet_rewrites": [
                "Rewrite bullets as: Action verb + technical scope + measurable business or engineering outcome.",
                "Lead each bullet with the JD skill when that skill is genuinely represented in your work.",
            ],
            "quantification_improvements": [
                "Add metrics for latency, reliability, cost, revenue, users, throughput, time saved, or quality gains.",
                "Convert vague ownership claims into measurable delivery statements.",
            ],
            "ats_optimization_tips": [
                "Use standard headings such as Summary, Skills, Experience, Projects, Education, and Certifications.",
                "Avoid tables, graphics, and keyword stuffing; repeat important terms naturally in context.",
            ],
        }

    def _cover_letter(self, resume_text: str, job_title: str, company: str, present: tuple[str, ...]) -> str:
        strengths = ", ".join(present[:5]) or "relevant technical delivery"
        resume_summary = shorten(" ".join(resume_text.split()), width=180, placeholder="...") or "my background"
        return (
            f"Dear Hiring Team,\n\nI am excited to apply for the {job_title} role at {company}. "
            f"My background includes {strengths}, and I have demonstrated this through work such as {resume_summary}. "
            "I would welcome the opportunity to help your team deliver reliable, measurable outcomes while continuing "
            "to build solutions aligned with the role's requirements.\n\nSincerely,\nCandidate"
        )

    def _resume_rewrite(
        self,
        resume_text: str,
        job_title: str,
        present: tuple[str, ...],
        missing: tuple[str, ...],
    ) -> str:
        cleaned_resume = _remove_years_of_experience(resume_text.strip())
        skills = ", ".join(dict.fromkeys((*present, *missing[:8]))) or "Add verified role-specific skills here"
        source = cleaned_resume or "Add verified resume details here before submitting."
        return (
            f"Target Role: {job_title}\n\n"
            f"Professional Summary\nATS-optimized candidate profile aligned to {job_title}, emphasizing verified strengths in {skills}.\n\n"
            f"Core Skills\n{skills}\n\n"
            "Selected Experience and Projects\n"
            f"- {shorten(source, width=220, placeholder='...')}\n"
            "- Reframe each original achievement with measurable scope, technical tools used, and business or engineering impact.\n"
            "- Add only accurate metrics and keywords supported by real project or employment history.\n\n"
            "Education and Certifications\nInclude verified degrees, certifications, and relevant coursework from the original resume."
        )


def _percent(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


def _remove_years_of_experience(text: str) -> str:
    patterns = [
        r"\b\d+\+?\s*(?:years|yrs)\s+of\s+experience\b",
        r"\b\d+\+?\s*(?:years|yrs)\b",
        r"\bover\s+\d+\s*(?:years|yrs)\b",
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "relevant experience", cleaned, flags=re.IGNORECASE)
    return cleaned
