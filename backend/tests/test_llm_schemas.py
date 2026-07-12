"""Regression test for a real, silent production bug: phishing_agent.py's response
schema used JSON-Schema-style `{"type": ["string", "null"]}` for a nullable field.
Gemini's schema dialect doesn't support a list of types — only a single `type` plus a
`nullable: true` flag — so the SDK's own schema validation rejected it on every single
call, silently sending every phishing analysis down the rule-based fallback path instead
of the real LLM. This validates every response schema in the codebase the same way
google-genai does internally, without needing a network call, so this class of bug fails
fast in CI instead of only surfacing as an unexplained 100% fallback rate in production.
"""
from google.genai import types

from app.services.claims_agent import _RESPONSE_SCHEMA as MEDIA_CLAIMS_SCHEMA
from app.services.phishing_agent import _RESPONSE_SCHEMA as PHISHING_SCHEMA


def test_media_claims_schema_is_valid_gemini_schema():
    types.Schema.model_validate(MEDIA_CLAIMS_SCHEMA)


def test_phishing_schema_is_valid_gemini_schema():
    types.Schema.model_validate(PHISHING_SCHEMA)


def test_phishing_schema_claimed_sender_is_properly_nullable():
    """The exact regression: a single STRING type with nullable=True, not a type list."""
    schema = types.Schema.model_validate(PHISHING_SCHEMA)
    claimed_sender = schema.properties["claimed_sender"]
    assert claimed_sender.type == types.Type.STRING
    assert claimed_sender.nullable is True
