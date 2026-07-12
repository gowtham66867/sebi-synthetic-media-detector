"""Coordinates the phishing-detection pipeline for one submitted email/message.

Stages:
  1. claims  -> LLM structured-extraction agent (claimed sender, URLs, requested actions, red flags)
  2. lexicon -> deterministic phishing-phrase scan of the raw text
  3. risk    -> weighted scoring + grounded LLM narrative synthesis

Shares the same job store as the media pipeline (orchestrator.py) — Firestore
in production, in-memory for local dev — so job IDs from either pipeline poll
through the same /api/*/jobs/{id} shape.
"""
from __future__ import annotations

import threading
import traceback
import uuid

from app.services import lexicon, phishing_agent, phishing_risk_engine
from app.services.job_store import build_job_store
from app.services.secrets import redact

_STAGES = ["claims", "lexicon", "risk"]

_store = build_job_store()


def start_job(text: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    _store.create(job_id, _STAGES)
    thread = threading.Thread(target=_run_pipeline, args=(job_id, text), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)


def _run_pipeline(job_id: str, text: str):
    try:
        _store.set_stage(job_id, "claims", "running")
        claims = phishing_agent.analyze_text(text)
        _store.set_stage(job_id, "claims", "done")

        _store.set_stage(job_id, "lexicon", "running")
        lexicon_hits = lexicon.scan_phishing_text(text)
        _store.set_stage(job_id, "lexicon", "done")

        _store.set_stage(job_id, "risk", "running")
        evidence = phishing_risk_engine.compute_phishing_risk(claims, lexicon_hits)
        evidence["message_text"] = text
        _store.set_stage(job_id, "risk", "done")

        _store.complete(job_id, evidence)
    except Exception as exc:
        _store.fail(job_id, redact(f"{exc}\n{traceback.format_exc()}"))
