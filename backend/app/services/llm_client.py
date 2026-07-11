"""Thin wrapper around the Gemini call sites used by claims_agent and risk_engine.

Both callers treat a None return as "LLM unavailable" and fall back to a
deterministic rule-based path — this is what keeps the pipeline demoable even
if the API key runs out of quota mid-demo (a real failure mode we hit while
building this).
"""
from __future__ import annotations

import logging

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


def try_generate_json(contents: str, system_instruction: str, schema: dict) -> dict | None:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        import json
        return json.loads(resp.text)
    except Exception as exc:
        logger.warning("Gemini JSON call failed, falling back to rule-based path: %s", exc)
        return None


def try_generate_text(contents: str, system_instruction: str) -> str | None:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2),
        )
        return resp.text.strip()
    except Exception as exc:
        logger.warning("Gemini text call failed, falling back to templated summary: %s", exc)
        return None
