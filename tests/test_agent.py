from job_scout_agent.agent import JobScoutAgent
from job_scout_agent.models import Job, SearchRequest, utc_now
from job_scout_agent.providers import JobProvider


class StaticProvider(JobProvider):
    name = "greenhouse"

    def search(self, request):
        return [
            Job(
                id="1",
                title="Python AI Agent Engineer",
                company="Remote Co",
                portal="greenhouse",
                apply_url="https://example.com/1",
                description="Python AI agents retrieval FastAPI LLM evaluation observability",
                location="Remote - Europe",
                remote=True,
                country="Germany",
                posted_at=utc_now(),
            ),
            Job(
                id="2",
                title="Java Developer",
                company="India Co",
                portal="greenhouse",
                apply_url="https://example.com/2",
                description="Java Spring backend payments",
                location="Pune, India",
                remote=False,
                country="India",
                posted_at=utc_now(),
            ),
        ]


def test_agent_scores_and_prioritizes_remote_outside_india():
    agent = JobScoutAgent(providers=[StaticProvider()])
    request = SearchRequest(
        resume_text="Built Python AI agents with FastAPI, retrieval, LLM evaluation, and observability.",
        designations=("engineer",),
        portals=("greenhouse",),
    )

    results = agent.search(request)

    assert len(results) == 2
    assert results[0].job.is_remote_outside_india is True
    assert results[0].fit.score > results[1].fit.score
    assert results[0].ats_analyzer_action["endpoint"] == "/ats/analyze"
