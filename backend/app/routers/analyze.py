import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import UPLOAD_DIR
from app.services import orchestrator

router = APIRouter(prefix="/api")

_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".ogg"}
_CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIXES)}")

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:10]}{suffix}"
    total = 0
    with dest.open("wb") as out:
        while chunk := await file.read(_CHUNK_SIZE):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit")
            out.write(chunk)

    job_id = orchestrator.start_job(dest)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
