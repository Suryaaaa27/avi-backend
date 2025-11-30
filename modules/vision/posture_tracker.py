# backend/modules/vision/posture_tracker.py

"""
Reliable posture analyzer for Windows + WebM uploads.
Uses:
- ffmpeg to convert webm → h264 mp4 (safe pixel format)
- Haar cascade face detection for posture/centering
- Sampling frames (8–12 frames total)
"""

import os
import cv2
import tempfile
import shutil
import subprocess
import numpy as np

def _ffmpeg_convert_to_mp4(in_path, out_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-vf", "scale=640:-1:flags=lanczos",  # SAFE resize
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def analyze_posture(video_file):
    tmpdir = tempfile.mkdtemp(prefix="posture_")

    try:
        raw_path = os.path.join(tmpdir, "input.webm")
        mp4_path = os.path.join(tmpdir, "video.mp4")

        # Save uploaded file
        video_file.save(raw_path)

        # Convert → mp4
        _ffmpeg_convert_to_mp4(raw_path, mp4_path)

        if not os.path.exists(mp4_path):
            return {"success": False, "error": "ffmpeg conversion to mp4 failed."}

        # Try to load with ffmpeg backend first
        cap = cv2.VideoCapture(mp4_path, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(mp4_path)
            if not cap.isOpened():
                return {"success": False, "error": "Could not open video after conversion."}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15
        step = max(1, total_frames // 10)

        # Haar model
        face_xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(face_xml)

        sampled = 0
        presence_scores = []

        frame_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % step == 0:
                sampled += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                faces = face_cascade.detectMultiScale(gray, 1.2, 5)

                if len(faces) > 0:
                    presence_scores.append(1.0)
                else:
                    presence_scores.append(0.0)

            frame_index += 1

        cap.release()

        if sampled == 0:
            return {"success": False, "error": "Not enough video frames to analyze."}

        presence_ratio = float(np.mean(presence_scores))

        summary = (
            "good" if presence_ratio > 0.7 else
            "fair" if presence_ratio > 0.35 else
            "poor"
        )

        return {
            "success": True,
            "frames_sampled": sampled,
            "person_presence_ratio": presence_ratio,
            "summary": summary
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
