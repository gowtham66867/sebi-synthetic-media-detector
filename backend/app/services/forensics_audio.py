"""Heuristic voice-synthesis / cloning artifact detector.

Real forensic labs use deep classifiers trained on large deepfake-audio corpora.
For this prototype we compute the same signal-processing features those
classifiers are seeded with, and combine them into an explainable risk score —
every number in the output can be pointed at and defended to a judge.
"""
from dataclasses import dataclass, field

import librosa
import numpy as np


@dataclass
class AudioForensicsResult:
    synthetic_voice_score: float  # 0-1, higher = more likely synthetic
    signals: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def analyze_audio(audio_path: str) -> AudioForensicsResult:
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    notes = []
    signals = {}

    if len(y) < sr * 0.5:
        return AudioForensicsResult(0.0, {}, ["Clip too short for reliable analysis."])

    # 1. Pitch (f0) micro-variation ("jitter"): natural voices have organic
    #    frame-to-frame pitch wobble; many TTS/voice-clone pipelines over-smooth f0.
    f0, voiced_flag, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr)
    f0_voiced = f0[voiced_flag] if f0 is not None else np.array([])
    if f0_voiced.size > 5:
        jitter = float(np.mean(np.abs(np.diff(f0_voiced))) / (np.mean(f0_voiced) + 1e-6))
    else:
        jitter = None
    signals["pitch_jitter"] = jitter

    # 2. Spectral flatness: synthetic vocoders tend to produce a flatter,
    #    less "textured" spectrum than a real human larynx + room acoustics.
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
    signals["spectral_flatness"] = flatness

    # 3. High-frequency energy ratio: vocoder artifacts often show an unnatural
    #    roll-off or spike above 4kHz compared to natural speech recordings.
    stft = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    hf_mask = freqs > 4000
    hf_ratio = float(np.sum(stft[hf_mask, :]) / (np.sum(stft) + 1e-6))
    signals["high_freq_energy_ratio"] = hf_ratio

    # 4. MFCC frame-to-frame delta variance: natural coarticulation produces
    #    higher variance; some TTS output is comparatively "too smooth".
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_delta_var = float(np.mean(np.var(np.diff(mfcc, axis=1), axis=1)))
    signals["mfcc_delta_variance"] = mfcc_delta_var

    # 5. Silence-gap regularity: cloned voices stitched from TTS segments often
    #    have unnaturally uniform pause durations; natural speech pauses vary more.
    rms = librosa.feature.rms(y=y)[0]
    silence_mask = rms < (0.1 * np.max(rms) if np.max(rms) > 0 else 1)
    gap_runs = _run_lengths(silence_mask)
    gap_cv = float(np.std(gap_runs) / (np.mean(gap_runs) + 1e-6)) if len(gap_runs) > 2 else None
    signals["silence_gap_coeff_of_variation"] = gap_cv

    score = 0.0
    weight_total = 0.0

    if jitter is not None:
        # very low jitter -> suspicious over-smoothing
        s = _inverse_score(jitter, low=0.002, high=0.02)
        score += s * 0.25
        weight_total += 0.25
        if s > 0.6:
            notes.append("Unusually smooth pitch contour (low jitter) — consistent with synthesized speech.")

    s = _score_range(flatness, low=0.15, high=0.4)
    score += s * 0.2
    weight_total += 0.2
    if s > 0.6:
        notes.append("Elevated spectral flatness — spectrum lacks natural vocal texture.")

    s = _score_range(hf_ratio, low=0.02, high=0.15)
    score += s * 0.2
    weight_total += 0.2
    if s > 0.6:
        notes.append("Abnormal high-frequency energy distribution typical of vocoder artifacts.")

    s = _inverse_score(mfcc_delta_var, low=5, high=40)
    score += s * 0.2
    weight_total += 0.2
    if s > 0.6:
        notes.append("Low MFCC frame-to-frame variance — articulation appears too smooth/regular.")

    if gap_cv is not None:
        s = _inverse_score(gap_cv, low=0.3, high=1.2)
        score += s * 0.15
        weight_total += 0.15
        if s > 0.6:
            notes.append("Pause durations between phrases are unnaturally uniform.")

    final = score / weight_total if weight_total else 0.0
    if not notes:
        notes.append("No strong synthetic-voice artifacts detected in sampled signals.")

    return AudioForensicsResult(round(final, 3), signals, notes)


def _run_lengths(mask: np.ndarray) -> np.ndarray:
    runs = []
    count = 0
    for v in mask:
        if v:
            count += 1
        elif count:
            runs.append(count)
            count = 0
    if count:
        runs.append(count)
    return np.array(runs) if runs else np.array([0])


def _score_range(value: float, low: float, high: float) -> float:
    if value is None:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def _inverse_score(value: float, low: float, high: float) -> float:
    if value is None:
        return 0.0
    return float(np.clip((high - value) / (high - low), 0.0, 1.0))
