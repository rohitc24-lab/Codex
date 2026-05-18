"""Domain models for the job scout agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SearchRequest:
    """Input accepted by the job discovery agent.

    The user can provide a resume, one or more target designations, or both.
    """

    resume_text: str = ""
    designations: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    include_remote_outside_india: bool = True
    portals: tuple[str, ...] = ("linkedin", "greenhouse", "indeed")
    limit: int = 25


@dataclass(frozen=True)
class Job:
    """Normalized job record returned by any provider."""

    id: str
    title: str
    company: str
    portal: str
    apply_url: str
    description: str
    location: str = ""
    remote: bool = False
    country: str = ""
    posted_at: datetime | None = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_remote_outside_india(self) -> bool:
        """Return true when a job is remote and not India-bound."""

        country = self.country.strip().lower()
        location = self.location.strip().lower()
        india_markers = {"india", "in", "ind"}
        return self.remote and country not in india_markers and "india" not in location


@dataclass(frozen=True)
class JobFit:
    """Resume-to-job fit assessment."""

    score: int
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class JobResult:
    """Job result enriched with fit and front-end actions."""

    job: Job
    fit: JobFit
    ats_analyzer_action: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job": {
                "id": self.job.id,
                "title": self.job.title,
                "company": self.job.company,
                "portal": self.job.portal,
                "apply_url": self.job.apply_url,
                "description": self.job.description,
                "location": self.job.location,
                "remote": self.job.remote,
                "country": self.job.country,
                "posted_at": self.job.posted_at.isoformat() if self.job.posted_at else None,
                "active": self.job.active,
                "remote_outside_india": self.job.is_remote_outside_india,
                "metadata": self.job.metadata,
            },
            "fit": {
                "score": self.fit.score,
                "matched_keywords": list(self.fit.matched_keywords),
                "missing_keywords": list(self.fit.missing_keywords),
                "rationale": self.fit.rationale,
            },
            "ats_analyzer_action": self.ats_analyzer_action,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
