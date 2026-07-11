"""Aggregates every upstream agent's output into one explainable risk verdict.

Deterministic weighted scoring decides the number (so it's reproducible and
auditable); a final LLM call only narrates *why*, strictly grounded in the
structured evidence dict it's given — it is not allowed to invent new signals.
"""
import json
from dataclasses import asdict

from app.services import llm_client

_LEXICON_WEIGHT = {
    "impersonation_signal": 0.30,
    "insider_authority_claim": 0.20,
    "guaranteed_returns": 0.15,
    "unrealistic_multiplier": 0.15,
    "payment_solicitation": 0.15,
    "urgency_pressure": 0.05,
}

_SYNTHESIS_SYSTEM_PROMPT = """You are the final-report writer for an automated market-fraud triage tool used \
by a securities regulator's surveillance team. You will be given structured evidence (media forensics scores, \
transcript claims, registry-match results, lexicon hits) and a computed risk score. Write a concise, \
professional 4-6 sentence summary for a human analyst: state the risk level, cite the 2-4 strongest pieces of \
evidence by name, and end with one recommended next action (e.g. "escalate for manual review", "monitor", \
"low priority — likely benign"). Do not invent evidence not present in the input. Do not use markdown."""


def compute_risk(
    audio_result,
    video_result,
    claims: dict,
    registry_matches: list,
    lexicon_hits: dict,
) -> dict:
    lexicon_score = sum(_LEXICON_WEIGHT.get(cat, 0.05) for cat in lexicon_hits)
    lexicon_score = min(lexicon_score, 1.0)

    impersonation_penalty = 0.0
    for m in registry_matches:
        if m.verdict == "no_match" and m.match_score < 40:
            continue  # no claimed identifiable person, nothing to penalize
        if m.verdict in ("no_match",):
            impersonation_penalty = max(impersonation_penalty, 0.5)
        if m.verdict == "verified_but_expired_or_suspended":
            impersonation_penalty = max(impersonation_penalty, 0.8)

    media_score = 0.6 * video_result.synthetic_video_score + 0.4 * audio_result.synthetic_voice_score

    weights = {"media_forensics": 0.35, "lexicon": 0.30, "registry": 0.20, "intent": 0.15}
    intent_score = 0.7 if claims.get("overall_intent") == "stock_promotion" else (
        0.4 if claims.get("overall_intent") == "investment_advice" else 0.0
    )

    final_score = (
        weights["media_forensics"] * media_score
        + weights["lexicon"] * lexicon_score
        + weights["registry"] * impersonation_penalty
        + weights["intent"] * intent_score
    )
    final_score = round(min(final_score, 1.0), 3)

    if final_score >= 0.66:
        level = "HIGH"
    elif final_score >= 0.35:
        level = "MEDIUM"
    else:
        level = "LOW"

    evidence = {
        "risk_score": final_score,
        "risk_level": level,
        "media_forensics": {
            "audio": asdict(audio_result),
            "video": asdict(video_result),
        },
        "transcript_claims": claims,
        "registry_matches": [
            {
                "claimed_name": m.claimed_name,
                "match_score": m.match_score,
                "verdict": m.verdict,
                "matched_record": m.matched_record,
            }
            for m in registry_matches
        ],
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
    reasons = []

    for note in evidence["media_forensics"]["audio"]["notes"] + evidence["media_forensics"]["video"]["notes"]:
        if "No strong" not in note and "too short" not in note:
            reasons.append(note)

    for m in evidence["registry_matches"]:
        if m["verdict"] == "no_match":
            reasons.append(f"'{m['claimed_name']}' does not match any registered intermediary.")
        elif m["verdict"] == "verified_but_expired_or_suspended":
            reasons.append(f"'{m['claimed_name']}' matches a registry record that is expired or suspended.")

    for category, phrases in evidence["lexicon_hits"].items():
        reasons.append(f"transcript contains {category.replace('_', ' ')} language (\"{phrases[0]}\").")

    action = {
        "HIGH": "Escalate for manual analyst review.",
        "MEDIUM": "Flag for monitoring and secondary review.",
        "LOW": "Low priority — likely benign, no action required.",
    }[level]

    if not reasons:
        reasons_text = "No strong forensic, lexicon, or registry red flags were found in this clip."
    else:
        reasons_text = " ".join(reasons[:4])

    return (
        f"Risk assessment: {level} ({score_pct}/100). {reasons_text} {action} "
        f"[Generated by rule-based fallback summarizer — LLM synthesis was unavailable for this run.]"
    )
