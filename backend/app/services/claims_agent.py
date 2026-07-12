"""Agent that reads a transcript and extracts structured, checkable claims.

Primary path: a Gemini call given a strict JSON schema (tool contract) so
downstream agents (registry check, risk engine) consume typed data instead of
free text. If the LLM call fails (quota/auth/network), extract_claims falls
back to a deterministic regex + lexicon-based extractor — lower recall, but
it keeps the pipeline usable end-to-end without any live API dependency.
"""
import re

from app.services import llm_client, lexicon

_SYSTEM_PROMPT = """You are a financial-fraud claims extraction agent for a securities-market \
regulator. Given a transcript of an audio/video clip circulating on social media, extract:
- claimed_entities: names of people/firms the speaker claims to be, represents, or cites as authority \
  (e.g. "SEBI", a named analyst, a brokerage). Include a role guess (regulator, advisor, analyst, company, unknown).
- financial_claims: specific investment claims made (stock names, promised returns, timelines).
- red_flag_phrases: verbatim short phrases matching classic market-fraud patterns (guaranteed returns, \
  urgency pressure, insider-tip claims, impersonation of authority, unrealistic multipliers, payment solicitation).
- overall_intent: one of "investment_advice", "stock_promotion", "general_talk", "unclear".
Return ONLY structured data matching the schema. Be conservative — only extract what is explicitly stated."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "claimed_entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role_guess": {"type": "string", "enum": ["regulator", "advisor", "analyst", "company", "unknown"]},
                },
                "required": ["name", "role_guess"],
            },
        },
        "financial_claims": {"type": "array", "items": {"type": "string"}},
        "red_flag_phrases": {"type": "array", "items": {"type": "string"}},
        "overall_intent": {
            "type": "string",
            "enum": ["investment_advice", "stock_promotion", "general_talk", "unclear"],
        },
    },
    "required": ["claimed_entities", "financial_claims", "red_flag_phrases", "overall_intent"],
}

_NAME_PATTERNS = [
    # Case-insensitivity is scoped to the trigger phrase only (via inline (?i:...)) —
    # applying it to the whole pattern let lowercase connector words like "from" match
    # the [A-Z] capture group too, so "I am Rakesh Gupta from SEBI..." over-captured
    # "Rakesh Gupta from" as the name instead of stopping at "Gupta".
    re.compile(r"\b(?i:i am|i'm|this is|myself)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2})"),
    re.compile(r"\b(?i:on behalf of)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,3})"),
]
_ADVISOR_HINTS = ("advisor", "advisory", "wealth", "consult")
_ANALYST_HINTS = ("research", "analyst", "analysis")
_CLAIM_KEYWORDS = re.compile(
    r"[^.!?]*\b(return|profit|multibagger|invest|buy|stock|guarantee|crorepati|allotment)[^.!?]*[.!?]",
    re.IGNORECASE,
)


def extract_claims(transcript: str) -> dict:
    if not transcript.strip():
        return {"claimed_entities": [], "financial_claims": [], "red_flag_phrases": [], "overall_intent": "unclear", "extraction_method": "llm"}

    result = llm_client.try_generate_json(f"Transcript:\n\n{transcript}", _SYSTEM_PROMPT, _RESPONSE_SCHEMA)
    if result is not None:
        result["extraction_method"] = "llm"
        return result

    fallback = _rule_based_extract(transcript)
    fallback["extraction_method"] = "rule_based_fallback"
    return fallback


def _rule_based_extract(transcript: str) -> dict:
    text_lower = transcript.lower()
    lexicon_hits = lexicon.scan_transcript(transcript)

    entities = []
    seen_names = set()
    for pattern in _NAME_PATTERNS:
        for match in pattern.finditer(transcript):
            name = match.group(1).strip()
            if name.lower() in seen_names or len(name) < 3:
                continue
            seen_names.add(name.lower())
            window = text_lower[max(0, match.start() - 20): match.end() + 40]
            role = "advisor" if any(h in window for h in _ADVISOR_HINTS) else (
                "analyst" if any(h in window for h in _ANALYST_HINTS) else "unknown"
            )
            entities.append({"name": name, "role_guess": role})

    if "impersonation_signal" in lexicon_hits or "insider_authority_claim" in lexicon_hits or "sebi" in text_lower:
        entities.append({"name": "SEBI", "role_guess": "regulator"})

    financial_claims = list({m.group(0).strip() for m in _CLAIM_KEYWORDS.finditer(transcript)})[:10]
    red_flags = sorted({phrase for phrases in lexicon_hits.values() for phrase in phrases})

    if "unrealistic_multiplier" in lexicon_hits or "guaranteed_returns" in lexicon_hits or "payment_solicitation" in lexicon_hits:
        intent = "stock_promotion"
    elif lexicon_hits or "invest" in text_lower or "stock" in text_lower:
        intent = "investment_advice"
    else:
        intent = "general_talk"

    return {
        "claimed_entities": entities,
        "financial_claims": financial_claims,
        "red_flag_phrases": red_flags,
        "overall_intent": intent,
    }
