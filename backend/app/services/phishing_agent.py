"""Agent that reads a suspicious email/message and extracts structured,
checkable phishing indicators — the "Layer 1: AI Threat Detection" capability
named in the brief (phishing emails) that the original build didn't cover at
all (it only handled deepfake video/audio).

Same shape as claims_agent.py: an LLM call constrained to a strict schema,
with a deterministic regex + lexicon fallback if the LLM is unavailable.
"""
from __future__ import annotations

import re

from app.services import lexicon, llm_client

_SYSTEM_PROMPT = """You are a phishing-detection agent for a securities-market regulator. Given the \
text of an email or message reported as suspicious, extract:
- claimed_sender: the name/organization the message claims to be from (e.g. "SEBI", a named broker, \
  a bank), or null if none is stated.
- urls_found: any URLs mentioned in the message, verbatim.
- requested_actions: what the message is asking the recipient to do (e.g. "click a link to verify KYC", \
  "reply with OTP", "pay a fee").
- red_flag_phrases: verbatim short phrases matching classic phishing patterns (credential harvesting, \
  urgency pressure, authority impersonation, requests for payment, generic greetings, suspicious links).
- verdict: one of "likely_phishing", "suspicious", "likely_legitimate", "unclear".
Return ONLY structured data matching the schema. Be conservative — only extract what is explicitly stated."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "claimed_sender": {"type": ["string", "null"]},
        "urls_found": {"type": "array", "items": {"type": "string"}},
        "requested_actions": {"type": "array", "items": {"type": "string"}},
        "red_flag_phrases": {"type": "array", "items": {"type": "string"}},
        "verdict": {
            "type": "string",
            "enum": ["likely_phishing", "suspicious", "likely_legitimate", "unclear"],
        },
    },
    "required": ["claimed_sender", "urls_found", "requested_actions", "red_flag_phrases", "verdict"],
}

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_SENDER_PATTERNS = [
    re.compile(r"\b(?i:from|regards|sincerely)[,:]?\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,3})"),
]

_URGENT_CATEGORIES = {"credential_harvesting", "authority_impersonation", "financial_request"}


def analyze_text(text: str) -> dict:
    if not text.strip():
        return {
            "claimed_sender": None,
            "urls_found": [],
            "requested_actions": [],
            "red_flag_phrases": [],
            "verdict": "unclear",
            "extraction_method": "llm",
        }

    result = llm_client.try_generate_json(f"Message:\n\n{text}", _SYSTEM_PROMPT, _RESPONSE_SCHEMA)
    if result is not None:
        result["extraction_method"] = "llm"
        return result

    fallback = _rule_based_analyze(text)
    fallback["extraction_method"] = "rule_based_fallback"
    return fallback


def _rule_based_analyze(text: str) -> dict:
    lexicon_hits = lexicon.scan_phishing_text(text)
    urls = _URL_PATTERN.findall(text)

    claimed_sender = None
    for pattern in _SENDER_PATTERNS:
        match = pattern.search(text)
        if match:
            claimed_sender = match.group(1).strip()
            break
    if claimed_sender is None and "sebi" in text.lower():
        claimed_sender = "SEBI"

    requested_actions = []
    if "credential_harvesting" in lexicon_hits:
        requested_actions.append("requests credential/KYC/OTP verification")
    if "financial_request" in lexicon_hits:
        requested_actions.append("requests a payment or transfer")
    if urls and "suspicious_link_language" in lexicon_hits:
        requested_actions.append("asks recipient to click a link")

    red_flags = sorted({phrase for phrases in lexicon_hits.values() for phrase in phrases})

    has_urgent_category = any(cat in lexicon_hits for cat in _URGENT_CATEGORIES)
    if has_urgent_category and urls:
        verdict = "likely_phishing"
    elif has_urgent_category or (urls and lexicon_hits):
        verdict = "suspicious"
    elif lexicon_hits:
        verdict = "suspicious"
    else:
        verdict = "likely_legitimate"

    return {
        "claimed_sender": claimed_sender,
        "urls_found": urls,
        "requested_actions": requested_actions,
        "red_flag_phrases": red_flags,
        "verdict": verdict,
    }
