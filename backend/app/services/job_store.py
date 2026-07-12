"""Job state storage, abstracted behind two backends.

The orchestrator originally kept job state in a plain process-local dict.
That breaks the moment Cloud Run runs more than one instance: a poll request
can land on an instance that never ran the job and get a false 404 for a
real, in-progress analysis. Firestore fixes that by making job state shared
across every instance. Local dev doesn't have (and shouldn't need) GCP
credentials on every laptop, so this falls back to the in-memory store when
Firestore isn't reachable — same graceful-degradation pattern as the LLM
call sites in llm_client.py.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

# Used by build_job_store() to confirm Firestore connectivity at startup. Must not match
# Firestore's reserved __*__ document-ID pattern (see build_job_store's docstring below).
_HEALTHCHECK_DOC_ID = "_startup_healthcheck"


class InMemoryJobStore:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, stages: list[str]) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "status": "running",
                "stages": {s: "pending" for s in stages},
                "result": None,
                "error": None,
            }

    def set_stage(self, job_id: str, stage: str, status: str) -> None:
        with self._lock:
            self._jobs[job_id]["stages"][stage] = status

    def complete(self, job_id: str, result: dict) -> None:
        with self._lock:
            self._jobs[job_id]["status"] = "completed"
            self._jobs[job_id]["result"] = result

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            self._jobs[job_id]["status"] = "failed"
            self._jobs[job_id]["error"] = error

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


class FirestoreJobStore:
    """Shared job state across every Cloud Run instance."""

    def __init__(self, collection: str = "synthetic_media_jobs"):
        from google.cloud import firestore

        self._client = firestore.Client()
        self._collection = self._client.collection(collection)

    def create(self, job_id: str, stages: list[str]) -> None:
        self._collection.document(job_id).set({
            "status": "running",
            "stages": {s: "pending" for s in stages},
            "result": None,
            "error": None,
        })

    def set_stage(self, job_id: str, stage: str, status: str) -> None:
        self._collection.document(job_id).update({f"stages.{stage}": status})

    def complete(self, job_id: str, result: dict) -> None:
        self._collection.document(job_id).update({"status": "completed", "result": result})

    def fail(self, job_id: str, error: str) -> None:
        self._collection.document(job_id).update({"status": "failed", "error": error})

    def get(self, job_id: str) -> dict | None:
        snapshot = self._collection.document(job_id).get()
        return snapshot.to_dict() if snapshot.exists else None


def build_job_store():
    import os

    if os.getenv("JOB_STORE") == "memory":
        logger.info("Job store: in-memory (forced via JOB_STORE=memory)")
        return InMemoryJobStore()
    try:
        store = FirestoreJobStore()
        store.get(_HEALTHCHECK_DOC_ID)  # cheap round-trip to confirm credentials/connectivity now, not on the first real job
        logger.info("Job store: Firestore (shared across instances)")
        return store
    except Exception as exc:
        logger.warning(
            "Job store: Firestore unavailable (%s) — falling back to in-memory store. "
            "Fine for local dev; on a multi-instance Cloud Run deployment this will lose "
            "jobs polled from a different instance than the one running them.",
            exc,
        )
        return InMemoryJobStore()
