"""Coordinates the multi-agent pipeline for one submitted media file.

Pipeline stages (each one an independent, individually-testable agent):
  1. extract      -> pull audio track + sampled frames via ffmpeg
  2. transcribe    -> faster-whisper speech-to-text
  3. claims        -> LLM structured-extraction agent (entities, claims, red flags)
  4. forensics     -> audio + video signal-processing heuristics (parallel-safe)
  5. registry      -> fuzzy cross-check of claimed entities vs mock SEBI registry
  6. lexicon       -> deterministic scam-phrase scan of the transcript
  7. risk          -> weighted scoring + grounded LLM narrative synthesis

Progress for each stage is written to a shared job store (Firestore in
production, in-memory for local dev — see job_store.py) so the frontend can
poll /api/jobs/{id} from any instance and render a live pipeline visualization.
"""
from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path

from app.services import claims_agent, forensics_audio, forensics_video, lexicon, media_extract, registry, risk_engine, transcription
from app.services.job_store import build_job_store
from app.services.secrets import redact

_STAGES = ["extract", "transcribe", "claims", "forensics", "registry", "lexicon", "risk"]

_store = build_job_store()


def start_job(media_path: Path) -> str:
    job_id = uuid.uuid4().hex[:12]
    _store.create(job_id, _STAGES)
    thread = threading.Thread(target=_run_pipeline, args=(job_id, media_path), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)


def _run_pipeline(job_id: str, media_path: Path):
    try:
        _store.set_stage(job_id, "extract", "running")
        audio_path = media_extract.extract_audio(media_path)
        has_video = media_extract.has_video_stream(media_path)
        frame_paths = media_extract.extract_frames(media_path) if has_video else []
        _store.set_stage(job_id, "extract", "done")

        _store.set_stage(job_id, "transcribe", "running")
        transcript_result = transcription.transcribe(str(audio_path))
        _store.set_stage(job_id, "transcribe", "done")

        _store.set_stage(job_id, "claims", "running")
        claims = claims_agent.extract_claims(transcript_result["full_text"])
        _store.set_stage(job_id, "claims", "done")

        _store.set_stage(job_id, "forensics", "running")
        audio_result = forensics_audio.analyze_audio(str(audio_path))
        video_result = forensics_video.analyze_frames(frame_paths)
        _store.set_stage(job_id, "forensics", "done")

        _store.set_stage(job_id, "registry", "running")
        registry_matches = registry.check_entities(claims["claimed_entities"])
        _store.set_stage(job_id, "registry", "done")

        _store.set_stage(job_id, "lexicon", "running")
        lexicon_hits = lexicon.scan_transcript(transcript_result["full_text"])
        _store.set_stage(job_id, "lexicon", "done")

        _store.set_stage(job_id, "risk", "running")
        evidence = risk_engine.compute_risk(audio_result, video_result, claims, registry_matches, lexicon_hits)
        evidence["transcript"] = transcript_result
        _store.set_stage(job_id, "risk", "done")

        _store.complete(job_id, evidence)
    except Exception as exc:
        _store.fail(job_id, redact(f"{exc}\n{traceback.format_exc()}"))
