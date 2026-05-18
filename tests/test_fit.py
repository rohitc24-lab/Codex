from job_scout_agent.fit import important_keywords, score_fit


def test_score_fit_reports_matches_and_missing_keywords():
    fit = score_fit(
        "Python FastAPI Kubernetes CI/CD metrics",
        "We need Python FastAPI LLM evaluation and observability",
    )

    assert fit.score > 0
    assert "python" in fit.matched_keywords
    assert "llm" in fit.missing_keywords


def test_keywords_ignore_common_words():
    assert "the" not in important_keywords("the Python engineer and the team")
