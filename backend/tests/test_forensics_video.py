from app.services.forensics_video import analyze_frames


def test_no_frames_returns_zero_with_note():
    """Covers TC F-04/audio-only path: no video stream must degrade gracefully, not crash."""
    result = analyze_frames([])

    assert result.synthetic_video_score == 0.0
    assert "no video stream" in result.notes[0].lower()
    assert result.signals == {}
