"""Cross-checks claimed entities against a (mock) SEBI registered-intermediary
registry. In production this would call the real SEBI intermediary lookup API;
here it's a local CSV standing in for that data source, exercised through the
same fuzzy-match logic a live integration would use — this is the RAG-style
grounding step: claims get checked against ground truth, not just judged on
face value by the LLM.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.config import DATA_DIR

_REGISTRY_PATH = DATA_DIR / "registered_advisors.csv"


@dataclass
class RegistryMatch:
    claimed_name: str
    matched_record: dict | None
    match_score: float
    verdict: str  # "verified_active" | "verified_but_expired_or_suspended" | "no_match" | "not_applicable"


def _load_registry() -> list[dict]:
    with open(_REGISTRY_PATH, newline="") as f:
        return list(csv.DictReader(f))


def check_entities(claimed_entities: list[dict]) -> list[RegistryMatch]:
    registry = _load_registry()
    results = []
    for entity in claimed_entities:
        name = entity.get("name", "").strip()
        role = entity.get("role_guess", "unknown")
        if not name or role == "unknown" or name.lower() in {"sebi", "reserve bank of india", "rbi"}:
            # Regulator-name impersonation is itself a red flag, handled by risk_engine's
            # impersonation_signal lexicon check rather than a registry lookup.
            results.append(RegistryMatch(name, None, 0.0, "not_applicable"))
            continue

        best, best_score = None, 0.0
        for record in registry:
            score = fuzz.token_sort_ratio(name.lower(), record["name"].lower())
            if score > best_score:
                best, best_score = record, score

        if best and best_score >= 80:
            verdict = "verified_active" if best["status"] == "Active" else "verified_but_expired_or_suspended"
            results.append(RegistryMatch(name, best, best_score, verdict))
        else:
            results.append(RegistryMatch(name, None, best_score, "no_match"))
    return results
