"""Coordinates the multi-agent pipeline for one submitted media file.

Pipeline stages (each one an independent, individually-testable agent):
  1. extract      -> pull audio track + sampled frames via ffmpeg
  2. transcribe    -> faster-whisper speech-to-text
  3. claims        -> LLM structured-extraction agent (entities, claims, red flags)
  4. forensics     -> audio + video signal-processing heuristics (parallel-safe)
  5. registry      -> fuzzy cross-check of claimed entities vs mock SEBI registry
  6. lexicon       -> deterministic scam-phrase scan of the transcript
  7. risk          -> weighted scoring + grounded LLM narrative synthesis

Progress for each stage is written to an in-memory job store so the frontend
can poll /api/jobs/{id} and render a live pipeline visualization.
"""
from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path

from app.services import claims_agent, forensics_audio, forensics_video, lexicon, media_extract, registry, risk_engine, transcription

JOBS: dict[str, dict] = {}

_STAGES = ["extract", "transcribe", "claims", "forensics", "registry", "lexicon", "risk"]


def start_job(media_path: Path) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "status": "running",
        "stages": {s: "pending" for s in _STAGES},
        "result": None,
        "error": None,
    }
    thread = threading.Thread(target=_run_pipeline, args=(job_id, media_path), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)


def _set_stage(job_id: str, stage: str, status: str):
    JOBS[job_id]["stages"][stage] = status


def _run_pipeline(job_id: str, media_path: Path):
    try:
        _set_stage(job_id, "extract", "running")
        audio_path = media_extract.extract_audio(media_path)
        has_video = media_extract.has_video_stream(media_path)
        frame_paths = media_extract.extract_frames(media_path) if has_video else []
        _set_stage(job_id, "extract", "done")

        _set_stage(job_id, "transcribe", "running")
        transcript_result = transcription.transcribe(str(audio_path))
        _set_stage(job_id, "transcribe", "done")

        _set_stage(job_id, "claims", "running")
        claims = claims_agent.extract_claims(transcript_result["full_text"])
        _set_stage(job_id, "claims", "done")

        _set_stage(job_id, "forensics", "running")
        audio_result = forensics_audio.analyze_audio(str(audio_path))
        video_result = forensics_video.analyze_frames(frame_paths)
        _set_stage(job_id, "forensics", "done")

        _set_stage(job_id, "registry", "running")
        registry_matches = registry.check_entities(claims["claimed_entities"])
        _set_stage(job_id, "registry", "done")

        _set_stage(job_id, "lexicon", "running")
        lexicon_hits = lexicon.scan_transcript(transcript_result["full_text"])
        _set_stage(job_id, "lexicon", "done")

        _set_stage(job_id, "risk", "running")
        evidence = risk_engine.compute_risk(audio_result, video_result, claims, registry_matches, lexicon_hits)
        evidence["transcript"] = transcript_result
        _set_stage(job_id, "risk", "done")

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["result"] = evidence
    except Exception as exc:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = f"{exc}\n{traceback.format_exc()}"
