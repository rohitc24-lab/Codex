"""Small web/API server for the job scout agent."""

from __future__ import annotations

import json
import os
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .agent import JobScoutAgent
from .ats import ATSAnalyzer
from .models import SearchRequest

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Job Scout Agent</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; color: #1f2937; }
    textarea, input { width: 100%; padding: .75rem; margin: .35rem 0 1rem; }
    button { background: #2563eb; color: white; border: 0; border-radius: .5rem; padding: .7rem 1rem; cursor: pointer; }
    .job { border: 1px solid #d1d5db; border-radius: .75rem; padding: 1rem; margin: 1rem 0; }
    .pill { display: inline-block; background: #ecfdf5; color: #047857; padding: .2rem .5rem; border-radius: 999px; font-size: .85rem; }
    .score { font-weight: 700; }
  </style>
</head>
<body>
  <h1>Job Scout Agent</h1>
  <p>Paste a resume or enter designations. Results include active portal links, remote-outside-India classification, fit score, and an ATS analyzer handoff button.</p>
  <label>Resume</label>
  <textarea id="resume" rows="8" placeholder="Paste resume text here"></textarea>
  <label>Designations (comma-separated)</label>
  <input id="designations" value="AI agent engineer, Python backend engineer" />
  <button onclick="searchJobs()">Find jobs</button>
  <div id="results"></div>
<script>
async function searchJobs() {
  const payload = {
    resume_text: document.getElementById('resume').value,
    designations: document.getElementById('designations').value.split(',').map(s => s.trim()).filter(Boolean),
    include_remote_outside_india: true
  };
  const response = await fetch('/search', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
  const data = await response.json();
  const results = document.getElementById('results');
  results.innerHTML = '';
  data.results.forEach(result => {
    const job = result.job;
    const fit = result.fit;
    const node = document.createElement('section');
    node.className = 'job';
    node.innerHTML = `
      <h2>${job.title} — ${job.company}</h2>
      <p><span class="pill">${job.portal}</span> ${job.location || ''} ${job.remote_outside_india ? '<span class="pill">Remote outside India</span>' : ''}</p>
      <p class="score">Fit score: ${fit.score}%</p>
      <p>${fit.rationale}</p>
      <p><strong>Matched:</strong> ${fit.matched_keywords.join(', ') || 'None yet'}</p>
      <p><strong>Missing:</strong> ${fit.missing_keywords.join(', ') || 'None'}</p>
      <p><a href="${job.apply_url}" target="_blank" rel="noopener">Open job</a></p>
      <button data-job-id="${job.id}">Run ATS analysis</button>
      <pre hidden></pre>`;
    node.querySelector('button').addEventListener('click', () => runAts(result, node.querySelector('pre')));
    results.appendChild(node);
  });
}
async function runAts(result, output) {
  const payload = { resume_text: document.getElementById('resume').value, job: result.job };
  const response = await fetch('/ats/analyze', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
  output.hidden = false;
  output.textContent = JSON.stringify(await response.json(), null, 2);
}
</script>
</body>
</html>
"""


class JobScoutHandler(BaseHTTPRequestHandler):
    agent = JobScoutAgent()
    ats_analyzer = ATSAnalyzer()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._send(HTTPStatus.OK, INDEX_HTML, content_type="text/html; charset=utf-8")
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        if self.path == "/search":
            request = SearchRequest(
                resume_text=str(payload.get("resume_text", "")),
                designations=tuple(payload.get("designations") or ()),
                locations=tuple(payload.get("locations") or ()),
                include_remote_outside_india=bool(payload.get("include_remote_outside_india", True)),
                portals=tuple(payload.get("portals") or ("linkedin", "greenhouse", "indeed")),
                limit=int(payload.get("limit", 25)),
            )
            results = [result.to_dict() for result in self.agent.search(request)]
            self._send_json(HTTPStatus.OK, {"results": results})
            return
        if self.path == "/ats/analyze":
            self._send_json(HTTPStatus.OK, run_ats_handoff(payload, self.ats_analyzer))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), content_type="application/json")

    def _send(self, status: HTTPStatus, body: str | bytes, *, content_type: str) -> None:
        encoded = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_ats_handoff(payload: dict[str, Any], analyzer: ATSAnalyzer | None = None) -> dict[str, Any]:
    """Analyze locally or send the selected job and resume to an ATS analyzer webhook."""

    webhook = os.getenv("ATS_ANALYZER_WEBHOOK_URL")
    if webhook:
        request = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    job = payload.get("job") or {}
    resume_text = str(payload.get("resume_text", ""))
    active_analyzer = analyzer or ATSAnalyzer()
    return active_analyzer.analyze(resume_text, job)


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), JobScoutHandler)
    print(f"Job Scout Agent running on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
