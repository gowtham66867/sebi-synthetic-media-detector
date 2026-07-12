from app.services.job_store import InMemoryJobStore

_STAGES = ["extract", "transcribe", "claims", "forensics", "registry", "lexicon", "risk"]


def test_lifecycle():
    store = InMemoryJobStore()
    store.create("job-1", _STAGES)
    assert store.get("job-1")["status"] == "running"
    assert store.get("job-1")["stages"]["extract"] == "pending"

    store.set_stage("job-1", "extract", "running")
    assert store.get("job-1")["stages"]["extract"] == "running"

    store.complete("job-1", {"risk_score": 0.5})
    job = store.get("job-1")
    assert job["status"] == "completed"
    assert job["result"] == {"risk_score": 0.5}


def test_fail_records_error():
    store = InMemoryJobStore()
    store.create("job-2", _STAGES)
    store.fail("job-2", "boom")
    job = store.get("job-2")
    assert job["status"] == "failed"
    assert job["error"] == "boom"


def test_unknown_job_returns_none():
    store = InMemoryJobStore()
    assert store.get("does-not-exist") is None


def test_healthcheck_id_is_not_firestore_reserved():
    """Regression test for a real bug: Firestore rejects document IDs matching __*__ as
    reserved, so a healthcheck using such an ID always fails with 400 INVALID_ARGUMENT —
    even when Firestore itself is perfectly reachable — and the broad except in
    build_job_store() silently mistook that for "Firestore unreachable," always falling
    back to the in-memory store on Cloud Run rather than actually using Firestore there."""
    from app.services.job_store import _HEALTHCHECK_DOC_ID

    assert not (_HEALTHCHECK_DOC_ID.startswith("__") and _HEALTHCHECK_DOC_ID.endswith("__"))
