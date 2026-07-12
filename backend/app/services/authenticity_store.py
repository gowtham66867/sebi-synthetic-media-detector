"""Stores issued authenticity records (Layer 2), same two-backend shape as
job_store.py: Firestore in production so any instance can verify a record
issued on a different one, in-memory fallback for local dev.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_HEALTHCHECK_DOC_ID = "_startup_healthcheck"


class InMemoryAuthenticityStore:
    def __init__(self):
        self._records = {}
        self._lock = threading.Lock()

    def create(self, reference_id: str, record: dict) -> None:
        with self._lock:
            self._records[reference_id] = record

    def get(self, reference_id: str) -> dict | None:
        with self._lock:
            record = self._records.get(reference_id)
            return dict(record) if record else None


class FirestoreAuthenticityStore:
    def __init__(self, collection: str = "authenticity_records"):
        from google.cloud import firestore

        self._client = firestore.Client()
        self._collection = self._client.collection(collection)

    def create(self, reference_id: str, record: dict) -> None:
        self._collection.document(reference_id).set(record)

    def get(self, reference_id: str) -> dict | None:
        snapshot = self._collection.document(reference_id).get()
        return snapshot.to_dict() if snapshot.exists else None


def build_authenticity_store():
    if os.getenv("JOB_STORE") == "memory":
        logger.info("Authenticity store: in-memory (forced via JOB_STORE=memory)")
        return InMemoryAuthenticityStore()
    try:
        store = FirestoreAuthenticityStore()
        store.get(_HEALTHCHECK_DOC_ID)
        logger.info("Authenticity store: Firestore (shared across instances)")
        return store
    except Exception as exc:
        logger.warning(
            "Authenticity store: Firestore unavailable (%s) — falling back to in-memory store. "
            "Fine for local dev; on multi-instance Cloud Run this will fail to verify records "
            "issued on a different instance.",
            exc,
        )
        return InMemoryAuthenticityStore()
