import json

from app.config import DATA_DIR

_SCAM_LEXICON_PATH = DATA_DIR / "scam_lexicon.json"
_PHISHING_LEXICON_PATH = DATA_DIR / "phishing_lexicon.json"


def _scan(text: str, lexicon_path) -> dict[str, list[str]]:
    lexicon = json.loads(lexicon_path.read_text())
    text_lower = text.lower()
    hits = {}
    for category, phrases in lexicon.items():
        found = [p for p in phrases if p in text_lower]
        if found:
            hits[category] = found
    return hits


def scan_transcript(transcript: str) -> dict[str, list[str]]:
    return _scan(transcript, _SCAM_LEXICON_PATH)


def scan_phishing_text(text: str) -> dict[str, list[str]]:
    return _scan(text, _PHISHING_LEXICON_PATH)
