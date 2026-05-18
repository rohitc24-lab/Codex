from job_scout_agent.ats import ATSAnalyzer
from job_scout_agent.server import run_ats_handoff


def test_ats_analyzer_returns_required_six_steps_without_years_language():
    analyzer = ATSAnalyzer()
    result = analyzer.analyze(
        "Built Python FastAPI services and AI agents. 5 years of experience with AWS.",
        {
            "id": "job-1",
            "title": "AI Agent Engineer",
            "company": "RemoteFirst Labs",
            "description": "Python FastAPI AI agents LLM retrieval evaluation observability AWS",
        },
    )

    assert result["status"] == "completed"
    assert 0 <= result["step_1_ats_score"]["overall_score"] <= 100
    assert "skills_match" in result["step_1_ats_score"]["breakdown"]
    assert result["step_2_gap_analysis"]["critical_gaps"]
    assert "python" in result["step_3_keyword_matching"]["present"]
    assert "cover letter" not in result["step_5_cover_letter"].lower()
    assert "5 years" not in result["step_6_resume_rewrite"].lower()


def test_ats_handoff_uses_local_analyzer_when_webhook_is_not_configured(monkeypatch):
    monkeypatch.delenv("ATS_ANALYZER_WEBHOOK_URL", raising=False)

    result = run_ats_handoff(
        {
            "resume_text": "Designed Python APIs with observability.",
            "job": {"title": "Backend Engineer", "description": "Python APIs observability"},
        }
    )

    assert result["status"] == "completed"
    assert "step_6_resume_rewrite" in result
