import numpy as np
import soundfile as sf

from app.services.forensics_audio import analyze_audio


def _write_tone(path, duration, sr=16000, freq=180.0):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.2 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    sf.write(str(path), audio, sr)


def test_short_clip_short_circuits(tmp_path):
    """Covers TC E-05: sub-500ms clips must not go through full feature extraction."""
    wav_path = tmp_path / "short.wav"
    _write_tone(wav_path, duration=0.3)

    result = analyze_audio(str(wav_path))

    assert result.synthetic_voice_score == 0.0
    assert "too short" in result.notes[0].lower()
    assert result.signals == {}


def test_normal_clip_returns_bounded_score_with_signals(tmp_path):
    wav_path = tmp_path / "normal.wav"
    _write_tone(wav_path, duration=3.0)

    result = analyze_audio(str(wav_path))

    assert 0.0 <= result.synthetic_voice_score <= 1.0
    assert result.notes  # always at least the "no strong artifacts" default note
    assert "pitch_jitter" in result.signals
    assert "spectral_flatness" in result.signals
