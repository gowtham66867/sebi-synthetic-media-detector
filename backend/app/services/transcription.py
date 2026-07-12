from functools import lru_cache

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    return WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


_EMPTY_TRANSCRIPT = {"language": "unknown", "language_probability": 0.0, "segments": [], "full_text": ""}


def transcribe(audio_path: str) -> dict:
    model = _get_model()
    try:
        segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
    except ValueError:
        # faster-whisper's language-detection step does max() over per-segment language
        # votes; when the decoded audio has ~zero content frames (no audio track, a
        # near-silent clip, or VAD stripping everything as non-speech) that vote dict is
        # empty and max() raises. That's a legitimate "no speech here" outcome for our
        # pipeline, not a fatal error — the risk report should still be produced from
        # forensics/lexicon signals alone rather than the whole job failing.
        return dict(_EMPTY_TRANSCRIPT)

    text_segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
    full_text = " ".join(s["text"] for s in text_segments).strip()
    return {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "segments": text_segments,
        "full_text": full_text,
    }
