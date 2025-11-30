def detect_emotion(image_file):
    """
    Dummy emotion detector.
    We use tone and NLP modules for emotion now.
    This exists so pipeline does not break.
    """
    return {
        "success": True,
        "dominant_emotion": "neutral",
        "emotion_scores": {
            "neutral": 1.0
        }
    }
