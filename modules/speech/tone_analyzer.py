# backend/modules/speech/tone_analyzer.py
"""
Tone Analyzer
- Accepts Flask FileStorage (webm, mp3, wav)
- Converts to .wav using ffmpeg into a temp file
- Loads audio with librosa and runs a HF emotion model (wav2vec2-based)
- Returns JSON-serializable dict
"""

import os
import tempfile
import subprocess
import shutil
import numpy as np

# ML libs
import torch
import librosa
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification

# utils (optional helper you might have)
from utils.audio_utils import normalize_audio, extract_pitch  # keep if present; otherwise fallback

# MODEL (lazy load)
MODEL_NAME = "superb/wav2vec2-base-superb-er"
feature_extractor = None
model = None

def _load_model_once():
    global feature_extractor, model
    if feature_extractor is None or model is None:
        try:
            feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
            model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_NAME)
            model.eval()
            print("✅ Tone Analyzer model loaded successfully!")
        except Exception as e:
            print("⚠️ Tone Analyzer model load failed:", e)
            feature_extractor = None
            model = None

def _ffmpeg_convert_to_wav(in_path, out_wav_path):
    # overwrite if exists
    cmd = ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", out_wav_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def analyze_tone(audio_file):
    """
    audio_file: Flask FileStorage
    returns: dict JSON-serializable
    """
    _load_model_once()
    # If model disabled, return graceful
    if model is None or feature_extractor is None:
        return {"success": False, "error": "Tone model not loaded."}

    tmpdir = tempfile.mkdtemp(prefix="tone_")
    try:
        in_path = os.path.join(tmpdir, "input.webm")
        wav_path = os.path.join(tmpdir, "audio.wav")

        # Save incoming file
        audio_file.save(in_path)

        # Convert to wav
        _ffmpeg_convert_to_wav(in_path, wav_path)
        if not os.path.exists(wav_path):
            return {"success": False, "error": "ffmpeg conversion to wav failed."}

        # load
        y, sr = librosa.load(wav_path, sr=16000, mono=True)
        # normalize if helper exists
        try:
            y = normalize_audio(y)
        except Exception:
            # fallback: simple normalization
            if np.max(np.abs(y)) > 0:
                y = y / np.max(np.abs(y))

        # Feature extraction & model
        inputs = feature_extractor(y, sampling_rate=sr, return_tensors="pt", padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits
        probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().numpy()
        labels = model.config.id2label if hasattr(model.config, "id2label") else {i: str(i) for i in range(len(probs))}
        emotion_scores = {labels[i]: float(probs[i]) for i in range(len(probs))}
        detected_emotion = max(emotion_scores, key=emotion_scores.get)

        # pitch & energy (best-effort)
        try:
            pitch = float(extract_pitch(y, sr))
        except Exception:
            # simple median pitch fallback
            try:
                pitches, mag = librosa.piptrack(y=y, sr=sr)
                pitch_vals = pitches[pitches > 0]
                pitch = float(np.median(pitch_vals)) if pitch_vals.size else 0.0
            except Exception:
                pitch = 0.0

        energy = float(np.mean(librosa.feature.rms(y=y)))

        return {
            "success": True,
            "detected_emotion": detected_emotion,
            "emotion_scores": emotion_scores,
            "pitch": pitch,
            "energy": energy
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # cleanup
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
