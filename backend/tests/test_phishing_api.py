import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analyze_text_pipeline_completes():
    # Force the rule-based fallback path so this test never makes a real Gemini call —
    # same "no network required" guarantee as the rest of the suite.
    with (
        patch("app.services.phishing_agent.llm_client.try_generate_json", return_value=None),
        patch("app.services.phishing_risk_engine.llm_client.try_generate_text", return_value="canned summary"),
    ):
        resp = client.post(
            "/api/phishing/analyze",
            json={"text": "Dear Customer, verify your account immediately or it will be suspended."},
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        job = None
        for _ in range(50):
            job = client.get(f"/api/phishing/jobs/{job_id}").json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

    assert job["status"] == "completed", job.get("error")
    assert job["result"]["risk_score"] is not None
    assert "message_text" in job["result"]


def test_unknown_phishing_job_returns_404():
    resp = client.get("/api/phishing/jobs/does-not-exist")
    assert resp.status_code == 404


def test_analyze_text_rejects_empty_body():
    resp = client.post("/api/phishing/analyze", json={"text": ""})
    assert resp.status_code == 422
