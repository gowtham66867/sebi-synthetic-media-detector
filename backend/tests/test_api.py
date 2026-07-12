from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import UPLOAD_DIR
from app.main import app
from app.services import rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # All requests from TestClient share one IP ("testclient"), so without this every
    # test in this file would draw down the same rate-limit bucket and order would matter.
    rate_limiter._requests_by_ip = {}


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unsupported_file_type_rejected():
    """Covers TC E-01."""
    resp = client.post("/api/analyze", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_unknown_job_returns_404():
    """Covers TC E-06."""
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404


def test_oversized_upload_rejected():
    """Covers TC S-02: the upload size cap must actually reject, not just log a warning."""
    with patch("app.routers.analyze.MAX_UPLOAD_BYTES", 1000):
        oversized_payload = b"0" * 5000
        resp = client.post("/api/analyze", files={"file": ("clip.wav", oversized_payload, "audio/wav")})
    assert resp.status_code == 413


def test_upload_filename_is_not_client_controlled():
    """Covers TC S-01: the client-supplied filename must never reach the filesystem verbatim."""
    malicious_name = "../../etc/passed.wav"
    before = set(UPLOAD_DIR.iterdir())
    resp = client.post("/api/analyze", files={"file": (malicious_name, b"RIFF....fake-audio-content", "audio/wav")})
    try:
        assert resp.status_code == 200
        new_files = set(UPLOAD_DIR.iterdir()) - before
        assert new_files, "expected the upload to create exactly one file"
        for f in new_files:
            assert "passed" not in f.name
            assert ".." not in f.name
    finally:
        for f in set(UPLOAD_DIR.iterdir()) - before:
            f.unlink(missing_ok=True)


def test_analyze_rate_limited_returns_429(monkeypatch):
    """The one endpoint that triggers real compute cost (Whisper + Gemini) must cap abuse."""
    monkeypatch.setattr(rate_limiter, "_MAX_REQUESTS_PER_WINDOW", 2)
    before = set(UPLOAD_DIR.iterdir())
    try:
        payload = {"file": ("clip.wav", b"RIFF....fake-audio-content", "audio/wav")}
        assert client.post("/api/analyze", files=payload).status_code == 200
        assert client.post("/api/analyze", files=payload).status_code == 200
        resp = client.post("/api/analyze", files=payload)
        assert resp.status_code == 429
    finally:
        for f in set(UPLOAD_DIR.iterdir()) - before:
            f.unlink(missing_ok=True)


def test_client_ip_prefers_x_forwarded_for(monkeypatch):
    """Cloud Run terminates the connection at its load balancer — the real client IP
    only survives in X-Forwarded-For, not request.client.host."""
    captured = {}

    def fake_is_allowed(ip):
        captured["ip"] = ip
        return True

    monkeypatch.setattr(rate_limiter, "is_allowed", fake_is_allowed)
    before = set(UPLOAD_DIR.iterdir())
    try:
        client.post(
            "/api/analyze",
            files={"file": ("clip.wav", b"data", "audio/wav")},
            headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"},
        )
        assert captured["ip"] == "203.0.113.5"
    finally:
        for f in set(UPLOAD_DIR.iterdir()) - before:
            f.unlink(missing_ok=True)
