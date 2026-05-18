# Job Scout Agent

A resume-aware job discovery agent that can:

- accept either pasted resume text or target designations,
- query pluggable job portal providers such as Greenhouse plus LinkedIn/Indeed search-link adapters,
- classify remote jobs outside India,
- return active jobs with a transparent resume-to-description fit score, and
- render a **Run ATS analysis** button for every job that runs the included ATS Resume Analyzer or forwards to an external ATS service.

## Run locally

```bash
python -m job_scout_agent.server
```

Open <http://localhost:8000>.

## API

### `POST /search`

```json
{
  "resume_text": "Built Python AI agents with FastAPI and retrieval...",
  "designations": ["AI agent engineer", "Python backend engineer"],
  "locations": ["Remote"],
  "include_remote_outside_india": true,
  "portals": ["linkedin", "greenhouse", "indeed"],
  "limit": 25
}
```

The response includes normalized job fields, `remote_outside_india`, `fit`, and an `ats_analyzer_action` object that points to `/ats/analyze`.

### `POST /ats/analyze`

The web UI calls this endpoint when a user presses **Run ATS analysis**. By default it runs the included ATS analyzer using the supplied six-step scorer prompt and returns:

1. ATS score with Skills Match, Experience Relevance, Keyword Match, Role Alignment, and Education/Extras.
2. Gap analysis grouped as critical, moderate, and minor gaps.
3. Top 20 JD keywords with present, missing, and suggested additions.
4. Resume recommendations, bullet rewrites, quantification improvements, and ATS tips.
5. A concise tailored cover letter.
6. An ATS-optimized resume rewrite that avoids years-of-experience claims and does not fabricate experience.

To forward the same payload to an external ATS Resume Analyzer agent instead, set:

```bash
export ATS_ANALYZER_WEBHOOK_URL="https://your-ats-agent.example.com/analyze"
```

When this variable is present, the agent forwards the selected job and resume as JSON to that webhook instead of using the local analyzer.

## Portal integrations

This repository avoids brittle or terms-sensitive scraping. Add approved API or partner-feed providers by implementing `JobProvider` in `job_scout_agent/providers.py`.

Current adapters:

- `GreenhouseBoardProvider`: reads public Greenhouse board JSON for company board tokens in `GREENHOUSE_BOARDS`.
- `SearchUrlProvider`: creates active LinkedIn and Indeed remote search links when direct API credentials are not configured.
- `DemoProvider`: deterministic local data for development; disable with `JOB_SCOUT_USE_DEMO=0`.

Example Greenhouse setup:

```bash
export GREENHOUSE_BOARDS="openai,stripe,databricks"
python -m job_scout_agent.server
```

## Tests

```bash
python -m pytest
```
