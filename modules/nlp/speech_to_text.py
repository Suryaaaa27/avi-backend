# backend/modules/nlp/speech_to_text.py

import os
import tempfile
import subprocess
import shutil
import numpy as np
from config import Config

model = None

def get_whisper_model():
    global model
    if model is None:
        print(f"[INFO] Loading Whisper model: {Config.WHISPER_MODEL}")
        import whisper
        model = whisper.load_model(Config.WHISPER_MODEL)
    return model

def transcribe_audio(audio_file):
    try:
        whisper_model = get_whisper_model()

        tmpdir = tempfile.mkdtemp(prefix="transcribe_")

        try:
            # Save raw WEBM file
            raw_path = os.path.join(tmpdir, "input.webm")
            wav_path = os.path.join(tmpdir, "audio.wav")
            audio_file.save(raw_path)

            # Convert to WAV 16kHz MONO
            cmd = [
                "ffmpeg", "-y",
                "-i", raw_path,
                "-ac", "1",
                "-ar", "16000",
                wav_path
            ]

            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not os.path.exists(wav_path):
                return {
                    "success": False,
                    "error": f"ffmpeg conversion failed: {p.stderr.decode()}",
                    "text": "",
                    "language": ""
                }

            # Whisper transcription
            result = whisper_model.transcribe(wav_path)
            text = (result.get("text") or "").strip()

            # Sometimes Whisper returns empty text → pad frames
            if len(text) < 2:
                return {"success": False, "text": "", "language": "unknown", "error": "audio too short"}

            return {"success": True, "text": text, "language": result.get("language", "unknown")}

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "language": ""
        }
