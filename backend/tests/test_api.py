from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
