"""Strips known secret values out of text before it's stored or returned.

llm_client.py already catches Gemini-related exceptions internally, so a raw
API-key value shouldn't normally reach a job's public error field. This is
defense-in-depth for the other exceptions (ffmpeg, whisper, etc.) that do get
their full traceback text stored and served back via GET /api/jobs/{id}.
"""
from app.config import GEMINI_API_KEY

_REDACTED = "[REDACTED_API_KEY]"


def redact(text: str) -> str:
    if GEMINI_API_KEY and GEMINI_API_KEY in text:
        text = text.replace(GEMINI_API_KEY, _REDACTED)
    return text
