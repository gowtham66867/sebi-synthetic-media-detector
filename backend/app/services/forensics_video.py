"""Heuristic frame-level video-forgery artifact detector.

Same rationale as forensics_audio.py: rather than a black-box deep model we
compute known deepfake "tells" from the literature (blink irregularity,
blocking/frequency-domain inconsistency, face-boundary blending residue) on
sampled frames, so every score is explainable to a judge.
"""
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


@dataclass
class VideoForensicsResult:
    synthetic_video_score: float
    signals: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def analyze_frames(frame_paths: list[Path]) -> VideoForensicsResult:
    if not frame_paths:
        return VideoForensicsResult(0.0, {}, ["No video stream — audio-only analysis applied."])

    imgs = [cv2.imread(str(p)) for p in frame_paths]
    imgs = [im for im in imgs if im is not None]
    if not imgs:
        return VideoForensicsResult(0.0, {}, ["Could not decode video frames."])

    notes = []
    signals = {}

    # 1. Blink presence/rate across sampled frames: GAN/diffusion face-swaps
    #    historically under- or over-produce eye closures vs. natural ~15-20/min rate.
    eye_open_flags = []
    face_boxes = []
    for im in imgs:
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        faces = _FACE_CASCADE.detectMultiScale(gray, 1.2, 5, minSize=(60, 60))
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_boxes.append((x, y, w, h))
        face_roi = gray[y:y + h // 2, x:x + w]
        eyes = _EYE_CASCADE.detectMultiScale(face_roi, 1.1, 5)
        eye_open_flags.append(len(eyes) >= 1)

    face_detect_rate = len(face_boxes) / len(imgs)
    signals["face_detect_rate"] = round(face_detect_rate, 3)

    if len(eye_open_flags) > 4:
        toggles = sum(1 for a, b in zip(eye_open_flags, eye_open_flags[1:]) if a != b)
        blink_rate = toggles / len(eye_open_flags)
        signals["blink_toggle_rate"] = round(blink_rate, 3)
    else:
        blink_rate = None
        signals["blink_toggle_rate"] = None

    # 2. Frequency-domain blockiness: GAN-generated / heavily re-encoded faces
    #    often show unnatural high-frequency DCT energy concentration at face
    #    boundaries vs. the rest of the frame.
    dct_ratios = []
    for im, box in zip(imgs, face_boxes if face_boxes else [None] * len(imgs)):
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if box:
            x, y, w, h = box
            pad = int(0.15 * w)
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(gray.shape[1], x + w + pad), min(gray.shape[0], y + h + pad)
            region = gray[y0:y1, x0:x1]
        else:
            region = gray
        if region.size == 0:
            continue
        region = cv2.resize(region, (128, 128))
        dct = cv2.dct(region)
        hf_energy = np.sum(np.abs(dct[32:, 32:]))
        total_energy = np.sum(np.abs(dct)) + 1e-6
        dct_ratios.append(hf_energy / total_energy)

    dct_mean = float(np.mean(dct_ratios)) if dct_ratios else None
    dct_std = float(np.std(dct_ratios)) if len(dct_ratios) > 2 else None
    signals["face_hf_dct_ratio_mean"] = round(dct_mean, 4) if dct_mean is not None else None
    signals["face_hf_dct_ratio_std"] = round(dct_std, 4) if dct_std is not None else None

    # 3. Frame-to-frame face-region brightness jitter: face-swap compositing
    #    can leave a subtly flickering blend boundary absent in genuine footage.
    brightness_series = []
    for im, box in zip(imgs, face_boxes if face_boxes else [None] * len(imgs)):
        if not box:
            continue
        x, y, w, h = box
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        brightness_series.append(float(np.mean(gray[y:y + h, x:x + w])))
    brightness_jitter = float(np.std(np.diff(brightness_series))) if len(brightness_series) > 3 else None
    signals["face_brightness_jitter"] = round(brightness_jitter, 3) if brightness_jitter is not None else None

    score = 0.0
    weight_total = 0.0

    if face_detect_rate < 0.3:
        notes.append("Face detected in very few sampled frames — treat forensic score as low-confidence.")

    if blink_rate is not None:
        s = _band_score(blink_rate, ideal_low=0.05, ideal_high=0.35)
        score += s * 0.3
        weight_total += 0.3
        if s > 0.6:
            notes.append("Blink toggle pattern falls outside the natural range for sampled frame rate.")

    if dct_std is not None:
        s = _inverse_score(dct_std, low=0.002, high=0.02)
        score += s * 0.35
        weight_total += 0.35
        if s > 0.6:
            notes.append("Face-region frequency signature is unusually stable across frames (low natural variation).")

    if brightness_jitter is not None:
        s = _score_range(brightness_jitter, low=3, high=15)
        score += s * 0.35
        weight_total += 0.35
        if s > 0.6:
            notes.append("Face-region brightness flicker consistent with a composited/blended overlay.")

    final = (score / weight_total) if weight_total else 0.0
    if not notes:
        notes.append("No strong visual forgery artifacts detected in sampled frames.")

    return VideoForensicsResult(round(final, 3), signals, notes)


def _score_range(value, low, high) -> float:
    if value is None:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def _inverse_score(value, low, high) -> float:
    if value is None:
        return 0.0
    return float(np.clip((high - value) / (high - low), 0.0, 1.0))


def _band_score(value, ideal_low, ideal_high) -> float:
    """Score rises the further value falls outside the natural [ideal_low, ideal_high] band."""
    if value is None:
        return 0.0
    if ideal_low <= value <= ideal_high:
        return 0.0
    dist = min(abs(value - ideal_low), abs(value - ideal_high))
    return float(np.clip(dist / ideal_high, 0.0, 1.0))
