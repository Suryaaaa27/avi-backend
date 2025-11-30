# backend/utils/video_utils.py
import cv2
import numpy as np
import tempfile


def extract_frames(video_path, frame_rate=1):
    frames = []
    vidcap = cv2.VideoCapture(video_path)
    fps = vidcap.get(cv2.CAP_PROP_FPS)
    interval = int(fps / frame_rate) if fps > 0 else 1

    success, frame = vidcap.read()
    count = 0
    while success:
        if count % interval == 0:
            frames.append(frame)
        success, frame = vidcap.read()
        count += 1

    vidcap.release()
    return frames


def resize_frame(frame, width=640, height=480):
    return cv2.resize(frame, (width, height))


def convert_to_rgb(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def save_temp_video(file):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    file.save(tmp.name)
    return tmp.name


def preprocess_frame(frame):
    f = resize_frame(frame)
    f = convert_to_rgb(f)
    return f
