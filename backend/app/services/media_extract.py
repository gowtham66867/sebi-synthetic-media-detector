"""Extracts audio track and sampled frames from an uploaded media file via ffmpeg."""
import subprocess
import uuid
from pathlib import Path

from app.config import UPLOAD_DIR


def extract_audio(media_path: Path) -> Path:
    audio_path = media_path.with_name(f"{media_path.stem}_audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(media_path), "-ac", "1", "-ar", "16000", str(audio_path)],
        check=True, capture_output=True,
    )
    return audio_path


def extract_frames(media_path: Path, fps: float = 2.0, max_frames: int = 40) -> list[Path]:
    frame_dir = UPLOAD_DIR / f"frames_{uuid.uuid4().hex[:8]}"
    frame_dir.mkdir(exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(media_path),
            "-vf", f"fps={fps}", "-frames:v", str(max_frames),
            str(frame_dir / "frame_%04d.jpg"),
        ],
        check=True, capture_output=True,
    )
    return sorted(frame_dir.glob("frame_*.jpg"))


def has_video_stream(media_path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(media_path)],
        capture_output=True, text=True,
    )
    return "video" in result.stdout
