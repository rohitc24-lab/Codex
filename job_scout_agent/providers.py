"""Job portal provider adapters.

The agent keeps scraping-sensitive portals behind explicit adapters. Providers can use
public APIs, approved partner APIs, or organization-owned job board feeds. This keeps
LinkedIn/Indeed integrations compliant with each portal's access terms instead of
embedding brittle page scrapers.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Iterable

from .models import Job, SearchRequest, utc_now


class JobProvider(ABC):
    """Interface implemented by each portal adapter."""

    name: str

    @abstractmethod
    def search(self, request: SearchRequest) -> Iterable[Job]:
        """Return normalized active jobs for the given request."""


class SearchUrlProvider(JobProvider):
    """Fallback provider that creates active portal search links.

    Use this when direct API credentials are unavailable. It still lets the user open
    LinkedIn/Indeed searches for the exact designation while the agent handles providers
    with approved API access.
    """

    def __init__(self, name: str, url_template: str) -> None:
        self.name = name
        self.url_template = url_template

    def search(self, request: SearchRequest) -> Iterable[Job]:
        for designation in request.designations or ("software engineer",):
            query = urllib.parse.quote_plus(designation)
            url = self.url_template.format(query=query)
            yield Job(
                id=_stable_id(self.name, designation, url),
                title=f"{designation.title()} roles",
                company="Multiple companies",
                portal=self.name,
                apply_url=url,
                description=(
                    f"Open {self.name.title()} search results for active {designation} roles. "
                    "Connect an approved API key or partner feed for row-level results."
                ),
                location=", ".join(request.locations) or "Global / Remote",
                remote=True,
                country="Global",
                posted_at=utc_now(),
                active=True,
                metadata={"provider_type": "search_url"},
            )


class GreenhouseBoardProvider(JobProvider):
    """Read jobs from configured Greenhouse public board tokens.

    Configure GREENHOUSE_BOARDS as a comma-separated list such as
    ``openai,stripe,databricks``. Greenhouse public board JSON does not require a key
    for many company boards.
    """

    name = "greenhouse"

    def __init__(self, board_tokens: tuple[str, ...] | None = None) -> None:
        configured = os.getenv("GREENHOUSE_BOARDS", "")
        self.board_tokens = board_tokens or tuple(token.strip() for token in configured.split(",") if token.strip())

    def search(self, request: SearchRequest) -> Iterable[Job]:
        if not self.board_tokens:
            return ()
        jobs: list[Job] = []
        designation_terms = tuple(term.lower() for term in request.designations)
        for board in self.board_tokens:
            url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(board)}/jobs?content=true"
            try:
                with urllib.request.urlopen(url, timeout=8) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for item in payload.get("jobs", []):
                title = item.get("title", "")
                if designation_terms and not any(term in title.lower() for term in designation_terms):
                    continue
                location_name = (item.get("location") or {}).get("name", "")
                description = item.get("content") or item.get("absolute_url", "")
                jobs.append(
                    Job(
                        id=str(item.get("id") or _stable_id(board, title, location_name)),
                        title=title,
                        company=board,
                        portal=self.name,
                        apply_url=item.get("absolute_url", url),
                        description=description,
                        location=location_name,
                        remote="remote" in location_name.lower(),
                        country=_infer_country(location_name),
                        posted_at=_parse_datetime(item.get("updated_at")),
                        active=True,
                        metadata={"board": board, "provider_type": "greenhouse_board"},
                    )
                )
        return jobs


class DemoProvider(JobProvider):
    """Deterministic sample active jobs used for local development and tests."""

    name = "demo"

    def search(self, request: SearchRequest) -> Iterable[Job]:
        designation = (request.designations or ("AI agent engineer",))[0]
        return (
            Job(
                id="demo-remote-eu-agent-engineer",
                title=f"Senior {designation.title()}",
                company="RemoteFirst Labs",
                portal="greenhouse",
                apply_url="https://example.com/jobs/remote-eu-agent-engineer",
                description=(
                    "Build Python AI agents, retrieval workflows, FastAPI services, LLM evaluation, "
                    "automation tools, and production observability for distributed remote teams."
                ),
                location="Remote - Europe",
                remote=True,
                country="Germany",
                posted_at=utc_now(),
                active=True,
                metadata={"provider_type": "demo"},
            ),
            Job(
                id="demo-india-platform-engineer",
                title=f"{designation.title()} - Platform",
                company="Bengaluru Cloud Co",
                portal="indeed",
                apply_url="https://example.com/jobs/india-platform-engineer",
                description=(
                    "Develop cloud platform services with Python, Kubernetes, CI/CD, metrics, APIs, "
                    "and cross-functional engineering practices."
                ),
                location="Bengaluru, India",
                remote=False,
                country="India",
                posted_at=utc_now(),
                active=True,
                metadata={"provider_type": "demo"},
            ),
        )


def default_providers() -> tuple[JobProvider, ...]:
    providers: list[JobProvider] = [GreenhouseBoardProvider()]
    if os.getenv("JOB_SCOUT_USE_DEMO", "1") != "0":
        providers.append(DemoProvider())
    providers.extend(
        [
            SearchUrlProvider("linkedin", "https://www.linkedin.com/jobs/search/?keywords={query}&f_WT=2"),
            SearchUrlProvider("indeed", "https://www.indeed.com/jobs?q={query}&sc=0kf%3Aattr%28DSQF7%29%3B"),
        ]
    )
    return tuple(providers)


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"job-{digest}"


def _infer_country(location: str) -> str:
    normalized = location.lower()
    if "india" in normalized or "bengaluru" in normalized or "bangalore" in normalized:
        return "India"
    if "europe" in normalized:
        return "Europe"
    if "united states" in normalized or "usa" in normalized:
        return "United States"
    if "remote" in normalized:
        return "Global"
    return ""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
