"""Aggregates the phishing agent's output into an explainable risk verdict —
the phishing-detection sibling of risk_engine.py, same design: deterministic
weighted scoring for the number, a grounded LLM call (with a templated
fallback) only for the narration.
"""
from __future__ import annotations

import json

from app.services import llm_client

_LEXICON_WEIGHT = {
    "credential_harvesting": 0.30,
    "authority_impersonation": 0.25,
    "financial_request": 0.20,
    "urgency_pressure": 0.10,
    "suspicious_link_language": 0.10,
    "generic_greeting": 0.05,
}

_VERDICT_SCORE = {
    "likely_phishing": 0.8,
    "suspicious": 0.5,
    "unclear": 0.2,
    "likely_legitimate": 0.0,
}

_SYNTHESIS_SYSTEM_PROMPT = """You are the final-report writer for an automated phishing triage tool used \
by a securities regulator's surveillance team. You will be given structured evidence (extracted phishing \
indicators, lexicon hits, a computed risk score) for a reported email/message. Write a concise, professional \
4-6 sentence summary for a human analyst: state the risk level, cite the 2-4 strongest pieces of evidence by \
name, and end with one recommended next action. Do not invent evidence not present in the input. Do not use markdown."""


_OUT_OF_SCOPE_SUMMARY = (
    "This message does not match this tool's financial-phishing detection criteria (credential "
    "harvesting, urgency pressure, authority impersonation, payment requests). It contains language "
    "associated with a threat to life or physical safety, which this tool is not designed to assess. "
    "This is NOT a statement that the content is safe, benign, or legitimate — the absence of phishing "
    "signals is not a safety judgment. If this describes a genuine threat, report it immediately to the "
    "relevant law-enforcement or platform trust & safety channel."
)


def _wrong_tool_summary(scam_hits: dict) -> str:
    categories = ", ".join(cat.replace("_", " ") for cat in scam_hits)
    return (
        f"This message does not match this tool's financial-phishing detection criteria (credential "
        f"harvesting, urgency pressure, authority impersonation, payment requests), but it does contain "
        f"language associated with a different fraud pattern this tool doesn't screen for: {categories}. "
        f"This is NOT a statement that the content is legitimate — it means this specific check found "
        f"nothing, not that the message is safe. Investment-tip/stock-scam content like this is what the "
        f"'Suspect Clip' analyzer is built to score; this 'Suspicious Message' tool is scoped to phishing "
        f"emails/messages specifically."
    )


def compute_phishing_risk(
    claims: dict,
    lexicon_hits: dict,
    severe_content_hits: dict | None = None,
    scam_hits: dict | None = None,
) -> dict:
    if severe_content_hits or (scam_hits and not lexicon_hits):
        # Bypasses the phishing scoring machinery and any LLM call entirely: this path only needs to
        # be safe and deterministic, not clever. A phishing risk score is meaningless for content
        # that was never a phishing attempt in the first place, and "LOW RISK" would misrepresent
        # "no financial-phishing signals found" as "this content is safe" — exactly the failure mode
        # this branch exists to prevent, whether the content is a threat of violence or just fraud of
        # a different kind (investment scam language) that this specific tool isn't scoped to catch.
        summary = _OUT_OF_SCOPE_SUMMARY if severe_content_hits else _wrong_tool_summary(scam_hits)
        return {
            "risk_score": 0.0,
            "risk_level": "OUT_OF_SCOPE",
            "phishing_claims": claims,
            "lexicon_hits": lexicon_hits,
            "severe_content_hits": severe_content_hits or {},
            "scam_hits": scam_hits or {},
            "summary": summary,
        }

    lexicon_score = min(sum(_LEXICON_WEIGHT.get(cat, 0.05) for cat in lexicon_hits), 1.0)
    verdict_score = _VERDICT_SCORE.get(claims.get("verdict"), 0.2)
    url_score = 0.3 if claims.get("urls_found") else 0.0

    weights = {"lexicon": 0.40, "verdict": 0.40, "url_presence": 0.20}
    final_score = round(
        min(
            weights["lexicon"] * lexicon_score
            + weights["verdict"] * verdict_score
            + weights["url_presence"] * url_score,
            1.0,
        ),
        3,
    )

    if final_score >= 0.66:
        level = "HIGH"
    elif final_score >= 0.35:
        level = "MEDIUM"
    else:
        level = "LOW"

    evidence = {
        "risk_score": final_score,
        "risk_level": level,
        "phishing_claims": claims,
        "lexicon_hits": lexicon_hits,
    }
    evidence["summary"] = _synthesize_summary(evidence)
    return evidence


def _synthesize_summary(evidence: dict) -> str:
    text = llm_client.try_generate_text(json.dumps(evidence, default=str), _SYNTHESIS_SYSTEM_PROMPT)
    return text if text is not None else _template_summary(evidence)


def _template_summary(evidence: dict) -> str:
    level = evidence["risk_level"]
    score_pct = round(evidence["risk_score"] * 100)
    claims = evidence["phishing_claims"]
    reasons = []

    if claims.get("claimed_sender"):
        reasons.append(f"the message claims to be from '{claims['claimed_sender']}'.")
    if claims.get("urls_found"):
        reasons.append(f"it contains {len(claims['urls_found'])} embedded link(s).")
    for category in evidence["lexicon_hits"]:
        reasons.append(f"language matching {category.replace('_', ' ')} was detected.")

    action = {
        "HIGH": "Escalate for manual analyst review and consider blocking the sender/domain.",
        "MEDIUM": "Flag for monitoring and secondary review.",
        "LOW": "Low priority — likely benign, no action required.",
    }[level]

    reasons_text = " ".join(reasons[:4]) if reasons else "No strong phishing indicators were found."

    return (
        f"Risk assessment: {level} ({score_pct}/100). {reasons_text} {action} "
        f"[Generated by rule-based fallback summarizer — LLM synthesis was unavailable for this run.]"
    )
