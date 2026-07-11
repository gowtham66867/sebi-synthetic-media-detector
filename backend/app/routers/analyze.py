import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import UPLOAD_DIR
from app.services import orchestrator

router = APIRouter(prefix="/api")

_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".ogg"}


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIXES)}")

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:10]}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    job_id = orchestrator.start_job(dest)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
