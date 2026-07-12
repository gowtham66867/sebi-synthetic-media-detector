"""A small, honest preliminary check of the audio-forensics heuristics.

This is NOT a rigorous benchmark. n=5 per class, one TTS engine (macOS `say`),
one real-speech source (public-domain LibriVox recordings via Archive.org).
It exists because "we never validated this against a single real clip" was a
fair criticism, and a small real check is better than none — but it should not
be read as proof the heuristics work, only as directional evidence worth
following up with a proper labeled dataset (e.g. ASVspoof) before trusting the
scores in production. Requires macOS (`say`) and internet access; not run in CI.
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.forensics_audio import analyze_audio  # noqa: E402

WORKDIR = Path("/tmp/forensics_validation")
WORKDIR.mkdir(exist_ok=True)

REAL_SPEECH_URLS = [
    "https://archive.org/download/short_poetry_001_librivox/because_I_could_not_stop_for_death_dickinson_64kb.mp3",
    "https://archive.org/download/short_poetry_001_librivox/abou_hunt_py_64kb.mp3",
    "https://archive.org/download/short_poetry_001_librivox/dead_boche_graves_sm_64kb.mp3",
    "https://archive.org/download/short_poetry_001_librivox/heat_doolittle_ac_64kb.mp3",
    "https://archive.org/download/short_poetry_001_librivox/i_died_for_beauty_dickinson_ac_64kb.mp3",
]

SYNTH_SCRIPTS = [
    ("Samantha", "Good morning everyone. Today we will discuss the quarterly financial results and the outlook for the coming year."),
    ("Alex", "The stock market showed significant volatility this week as investors reacted to the latest economic data."),
    ("Victoria", "Please review the attached document carefully and let us know if you have any questions or concerns."),
    ("Daniel", "Our research team has identified several promising opportunities in the technology and healthcare sectors."),
    ("Karen", "Thank you for joining this call. We will begin with an overview of our strategic priorities for the year."),
]


def _fetch_real_samples() -> list[Path]:
    paths = []
    for i, url in enumerate(REAL_SPEECH_URLS, 1):
        mp3_path = WORKDIR / f"real_{i}.mp3"
        wav_path = WORKDIR / f"real_{i}.wav"
        if not wav_path.exists():
            urllib.request.urlretrieve(url, mp3_path)
            subprocess.run(["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "16000", "-ac", "1", "-t", "15", str(wav_path)],
                            check=True, capture_output=True)
        paths.append(wav_path)
    return paths


def _generate_synth_samples() -> list[Path]:
    paths = []
    for i, (voice, text) in enumerate(SYNTH_SCRIPTS, 1):
        aiff_path = WORKDIR / f"synth_{i}.aiff"
        wav_path = WORKDIR / f"synth_{i}.wav"
        if not wav_path.exists():
            subprocess.run(["say", "-v", voice, "-o", str(aiff_path), text], check=True)
            subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                            check=True, capture_output=True)
        paths.append(wav_path)
    return paths


def main():
    real_paths = _fetch_real_samples()
    synth_paths = _generate_synth_samples()

    real_scores = [analyze_audio(str(p)).synthetic_voice_score for p in real_paths]
    synth_scores = [analyze_audio(str(p)).synthetic_voice_score for p in synth_paths]

    print("real  scores:", [round(s, 3) for s in real_scores], "mean =", round(sum(real_scores) / len(real_scores), 3))
    print("synth scores:", [round(s, 3) for s in synth_scores], "mean =", round(sum(synth_scores) / len(synth_scores), 3))
    print()
    overlap = sum(1 for r in real_scores for s in synth_scores if r > s)
    print(f"directional check: synthetic mean {'>' if sum(synth_scores) > sum(real_scores) else '<='} real mean")
    print(f"{overlap}/{len(real_scores) * len(synth_scores)} (real, synth) pairs have real > synth — that's the overlap, not a clean separation")


if __name__ == "__main__":
    main()
