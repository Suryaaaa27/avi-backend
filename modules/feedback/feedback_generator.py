# backend/modules/feedback/feedback_generator.py

import json
from typing import Any, Dict
from utils.llm_client import rapidapi_chat_json, rapidapi_try_parse_json


# -------------------------------
# SCORING HELPER FUNCTIONS
# -------------------------------

def _norm_similarity(nlp: Dict[str, Any]) -> float:
    if not isinstance(nlp, dict):
        return 0.5

    s = nlp.get("similarity_score", nlp.get("score"))
    if s is None:
        return 0.5

    try:
        s = float(s)
    except:
        return 0.5

    if s > 1.5:
        s = s / 100.0

    return max(0.0, min(1.0, s))


def _emotion_score(emotion: Dict[str, Any]) -> float:
    if not isinstance(emotion, dict) or not emotion.get("success", True):
        return 0.7

    dom = (emotion.get("dominant_emotion") or "").lower()
    if dom in ("hap", "happy", "joy"):
        return 0.9
    if dom in ("neutral", "neu"):
        return 0.8
    if dom in ("sad", "ang", "angry", "fear"):
        return 0.6
    return 0.7


def _tone_score(tone: Dict[str, Any]) -> float:
    if not isinstance(tone, dict) or not tone.get("success", True):
        return 0.7

    dom = (tone.get("detected_emotion") or "").lower()
    if dom in ("hap", "happy", "excited"):
        return 0.9
    if dom in ("neutral", "neu", "calm"):
        return 0.8
    if dom in ("sad", "ang", "angry", "fear"):
        return 0.6
    return 0.7


def _posture_score(posture: Dict[str, Any]) -> float | None:
    if not isinstance(posture, dict) or not posture.get("success", True):
        return None

    summary = (posture.get("summary") or "").lower()
    if "excellent" in summary:
        return 0.9
    if "good" in summary:
        return 0.8
    if "poor" in summary or "bad" in summary:
        return 0.6
    return 0.7


def _merge_scores(nlp, emotion, posture, tone) -> float:
    nlp_s = _norm_similarity(nlp)
    emo_s = _emotion_score(emotion)
    tone_s = _tone_score(tone)
    post_s = _posture_score(posture)

    weights = {
        "nlp": 0.65,
        "emotion": 0.15,
        "tone": 0.10,
        "posture": 0.10,
    }

    if post_s is None:
        removed = weights.pop("posture")
        total = sum(weights.values())
        for k in weights:
            weights[k] += (weights[k] / total) * removed

    total = sum(weights.values())
    for k in weights:
        weights[k] /= total

    final_score = (
        weights["nlp"] * nlp_s +
        weights["emotion"] * emo_s +
        weights["tone"] * tone_s +
        weights.get("posture", 0) * (post_s or 0)
    )

    return max(0.0, min(1.0, final_score))


def _rating_from_score(score: float) -> str:
    if score >= 0.80:
        return "Excellent"
    if score >= 0.65:
        return "Good"
    if score >= 0.45:
        return "Average"
    return "Poor"


# -------------------------------
# MAIN FEEDBACK GENERATOR
# -------------------------------

def generate_feedback(nlp, emotion, posture, tone, email=None, interview_id=None):
    final_score = _merge_scores(nlp, emotion, posture, tone)
    rating = _rating_from_score(final_score)

    prompt_payload = {
        "nlp_result": nlp,
        "emotion_result": emotion,
        "posture_result": posture,
        "tone_result": tone,
        "final_score": final_score,
        "qualitative_rating": rating
    }

    prompt = f"""
You are a supportive interview coach.

Given the following JSON analysis:
{json.dumps(prompt_payload, indent=2, ensure_ascii=False)}

Write feedback in EXACT JSON format:

{{
  "feedback": "<full feedback text, structured like: summary, strengths, improvements, action plan>"
}}

Tone: encouraging, clear, respectful, never harsh.
"""

    try:
        model_text = rapidapi_chat_json(prompt)
        parsed = rapidapi_try_parse_json(model_text)
        feedback_text = parsed.get("feedback")

        if not feedback_text:
            raise ValueError("Missing feedback field")

    except Exception as e:
        percent = round(final_score * 100)
        feedback_text = (
            f"Fallback feedback due to error: {e}\n"
            f"Your approximate score is {percent}% ({rating}).\n"
            f"- Answer was short or unclear.\n"
            f"- Try speaking longer.\n"
        )

    return {
        "final_score": float(final_score),
        "qualitative_rating": rating,
        "nlp_result": nlp,
        "emotion_result": emotion,
        "tone_result": tone,
        "posture_result": posture,
        "feedback": feedback_text
    }
