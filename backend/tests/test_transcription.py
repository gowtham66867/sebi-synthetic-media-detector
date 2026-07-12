from unittest.mock import MagicMock, patch

from app.services import transcription


def test_transcribe_handles_empty_language_detection(tmp_path):
    """Regression test for a real production crash: faster-whisper's language-detection
    step does max() over per-segment language votes, and raises ValueError when the
    decoded audio has ~zero content frames (no audio track, near-silent clip, or VAD
    stripping everything as non-speech). That's a legitimate "no speech here" outcome,
    not a fatal pipeline error."""
    fake_model = MagicMock()
    fake_model.transcribe.side_effect = ValueError("max() arg is an empty sequence")

    with patch("app.services.transcription._get_model", return_value=fake_model):
        result = transcription.transcribe(str(tmp_path / "silent.wav"))

    assert result == {
        "language": "unknown",
        "language_probability": 0.0,
        "segments": [],
        "full_text": "",
    }


def test_transcribe_normal_path_unaffected():
    fake_segment = MagicMock(start=0.0, end=1.5, text=" hello world ")
    fake_info = MagicMock(language="en", language_probability=0.987)
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([fake_segment], fake_info)

    with patch("app.services.transcription._get_model", return_value=fake_model):
        result = transcription.transcribe("irrelevant.wav")

    assert result["full_text"] == "hello world"
    assert result["language"] == "en"
    assert result["language_probability"] == 0.987
    assert result["segments"] == [{"start": 0.0, "end": 1.5, "text": "hello world"}]
