from functools import lru_cache

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    return WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(audio_path: str) -> dict:
    model = _get_model()
    segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
    text_segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]
    full_text = " ".join(s["text"] for s in text_segments).strip()
    return {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "segments": text_segments,
        "full_text": full_text,
    }
