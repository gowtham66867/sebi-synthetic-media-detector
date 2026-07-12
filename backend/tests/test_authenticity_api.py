from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_issue_then_verify_roundtrip():
    issue_resp = client.post(
        "/api/authenticity/issue",
        json={"issuer": "SEBI", "communication_type": "circular", "content": "Trading hours extended Friday."},
    )
    assert issue_resp.status_code == 200
    body = issue_resp.json()
    assert body["reference_id"]
    assert body["qr_data_uri"].startswith("data:image/png;base64,")
    assert body["reference_id"] in body["verify_url"]

    verify_resp = client.get(f"/api/authenticity/verify/{body['reference_id']}")
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert verify_body["verified"] is True
    assert verify_body["issuer"] == "SEBI"
    assert verify_body["content"] == "Trading hours extended Friday."


def test_verify_unknown_reference_returns_not_verified():
    resp = client.get("/api/authenticity/verify/does-not-exist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["reason"] == "reference_not_found"


def test_issue_rejects_empty_content():
    resp = client.post("/api/authenticity/issue", json={"issuer": "SEBI", "content": ""})
    assert resp.status_code == 422
