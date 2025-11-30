# backend/utils/audio_utils.py
"""
Utility audio functions used by tone_analyzer.
Provides:
- normalize_audio
- extract_pitch
"""

import numpy as np
import librosa

# ---------------------------------------------
# SAFE NORMALIZATION
# ---------------------------------------------
def normalize_audio(y):
    """
    Normalize audio amplitude to [-1, 1].
    Avoids clipping and handles silent audio safely.
    """
    if y is None or len(y) == 0:
        return y

    peak = np.max(np.abs(y))
    if peak < 1e-6:   # silent
        return y

    return y / peak


# ---------------------------------------------
# PITCH EXTRACTION (Robust fallback pipeline)
# ---------------------------------------------
def extract_pitch(y, sr):
    """
    Extract pitch (fundamental frequency) from audio.
    Multi-stage fallback:
        1. librosa.pyin
        2. librosa.yin
        3. librosa.piptrack
        4. return 0.0
    Returns float pitch in Hz.
    """

    try:
        # -------- 1) Best method: PYIN --------
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=50,
            fmax=400,
            frame_length=2048,
            sr=sr
        )
        if f0 is not None:
            f0_clean = f0[~np.isnan(f0)]
            if len(f0_clean) > 0:
                return float(np.median(f0_clean))
    except Exception:
        pass

    try:
        # -------- 2) YIN (robust fallback) --------
        f0 = librosa.yin(y, fmin=50, fmax=400, sr=sr)
        if f0 is not None and len(f0) > 0:
            return float(np.median(f0))
    except Exception:
        pass

    try:
        # -------- 3) piptrack fallback --------
        pitches, mags = librosa.piptrack(y=y, sr=sr)
        p = pitches[pitches > 0]
        if p.size > 0:
            return float(np.median(p))
    except Exception:
        pass

    # -------- 4) Total fallback --------
    return 0.0
