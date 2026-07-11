import json

from app.config import DATA_DIR

_LEXICON_PATH = DATA_DIR / "scam_lexicon.json"


def scan_transcript(transcript: str) -> dict[str, list[str]]:
    lexicon = json.loads(_LEXICON_PATH.read_text())
    text = transcript.lower()
    hits = {}
    for category, phrases in lexicon.items():
        found = [p for p in phrases if p in text]
        if found:
            hits[category] = found
    return hits
