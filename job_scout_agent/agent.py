"""Main orchestration logic for the job scout agent."""

from __future__ import annotations

from collections.abc import Iterable

from .fit import score_fit
from .models import Job, JobResult, SearchRequest
from .providers import JobProvider, default_providers


class JobScoutAgent:
    """Search job portals, classify remote jobs, and prepare ATS handoff actions."""

    def __init__(self, providers: Iterable[JobProvider] | None = None) -> None:
        self.providers = tuple(providers or default_providers())

    def search(self, request: SearchRequest) -> list[JobResult]:
        jobs = self._collect_jobs(request)
        if request.include_remote_outside_india:
            jobs = sorted(jobs, key=lambda job: (not job.is_remote_outside_india, job.portal, job.title))
        results = [self._to_result(job, request.resume_text) for job in jobs[: request.limit]]
        return results

    def _collect_jobs(self, request: SearchRequest) -> list[Job]:
        requested_portals = {portal.lower() for portal in request.portals}
        jobs_by_key: dict[tuple[str, str, str], Job] = {}
        for provider in self.providers:
            if provider.name.lower() not in requested_portals and provider.name.lower() != "demo":
                continue
            for job in provider.search(request):
                if not job.active:
                    continue
                key = (job.title.lower(), job.company.lower(), job.apply_url)
                jobs_by_key[key] = job
        return list(jobs_by_key.values())

    def _to_result(self, job: Job, resume_text: str) -> JobResult:
        fit = score_fit(resume_text, job.description) if resume_text.strip() else score_fit(job.title, job.description)
        return JobResult(
            job=job,
            fit=fit,
            ats_analyzer_action={
                "label": "Run ATS analysis",
                "method": "POST",
                "endpoint": "/ats/analyze",
                "job_id": job.id,
            },
        )
