from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import rate_limiter, text_orchestrator

router = APIRouter(prefix="/api/phishing")

_MAX_TEXT_CHARS = 20_000


class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_TEXT_CHARS)


@router.post("/analyze")
async def analyze_text(request: Request, body: AnalyzeTextRequest):
    if not rate_limiter.is_allowed(rate_limiter.client_ip_from_request(request)):
        raise HTTPException(429, "Too many analysis requests from this address. Please try again later.")

    job_id = text_orchestrator.start_job(body.text)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = text_orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
