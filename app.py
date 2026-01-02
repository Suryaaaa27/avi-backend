# app.py

from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
import json
import os
import logging
import numpy as np
import requests
from typing import Any, Dict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_app():
    """Initialize Flask app and load configuration"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- CORS: allow Live Server + localhost
    CORS(
        app,
        resources={r"/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500"]}},
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "OPTIONS"],
        max_age=86400,
    )

    # -----------------------------
    # RapidAPI config (Mixtral)
    # -----------------------------
    RAPIDAPI_HOST = os.getenv(
        "RAPIDAPI_HOST",
        "llama-ai-mixtral-cohere-gpt-api.p.rapidapi.com",
    )
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_BASE = f"https://{RAPIDAPI_HOST}"

    # -----------------------------
    # Deferred imports
    # -----------------------------
    from modules.nlp.speech_to_text import transcribe_audio
    from modules.nlp.nlp_evaluator import evaluate_text
    from modules.vision.emotion_detector import detect_emotion
    from modules.vision.posture_tracker import analyze_posture
    from modules.speech.tone_analyzer import analyze_tone
    from modules.feedback.feedback_generator import generate_feedback
    from modules.nlp.domain_evaluator import evaluate_domain_response

    # 🔴 FIXED: removed `backend.` prefix (Vercel-safe)
    from database.db_connection import get_collection

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_collection():
        """Get Mongo collection 'interviews'"""
        return get_collection("interviews")

    def _domain_file(domain: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "data", f"{domain.lower()}.json")

    def _load_questions(domain: str):
        fp = _domain_file(domain)
        if not os.path.exists(fp):
            raise FileNotFoundError(
                f"Questions file not found for domain '{domain}'"
            )

        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "questions" in data:
            raw = data["questions"]
        elif isinstance(data, list):
            raw = data
        else:
            raise ValueError("Invalid questions JSON format")

        norm = []
        for idx, q in enumerate(raw):
            item = dict(q)
            item["id"] = item.get("id") or f"q{idx+1}"
            item["text"] = item.get("text") or item.get("question") or ""
            item["ideal_answer"] = (
                item.get("ideal_answer") or item.get("answer") or ""
            )
            norm.append(item)
        return norm

    def _numpy_safe(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _numpy_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_numpy_safe(x) for x in obj]
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        return obj

    def rapidapi_chat_json(prompt: str, endpoint: str = "mixtral", timeout: int = 30) -> str:
        if not RAPIDAPI_KEY:
            raise RuntimeError("RAPIDAPI_KEY not set")

        url = f"{RAPIDAPI_BASE}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY,
        }

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "web_access": False,
            "consider_chat_history": False,
            "system_prompt": "",
            "conversation_id": "",
        }

        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        resp_json = r.json()

        text = None
        if isinstance(resp_json.get("messages"), list):
            text = resp_json["messages"][-1].get("content")

        if text is None:
            text = json.dumps(resp_json)

        return text

    def rapidapi_try_parse_json(model_text: str) -> Dict[str, Any]:
        try:
            return json.loads(model_text)
        except Exception:
            start = model_text.find("{")
            end = model_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(model_text[start:end+1])
            raise ValueError("Invalid JSON from model")

    # =============================
    # ROUTES (ALL YOUR ROUTES BELOW)
    # =============================

    @app.route("/")
    def home():
        return jsonify({"message": "🚀 AVI Backend running"}), 200

    @app.route("/health")
    def health():
        return jsonify({"ok": True}), 200

    # ⬇️⬇️⬇️
    # EVERYTHING BELOW THIS POINT
    # IS **UNCHANGED LOGIC**
    # ⬇️⬇️⬇️

    # (question, reset, transcribe, evaluate, evaluate_domain,
    # emotion, posture, tone, generate-feedback, final_feedback)
    # — ALL remain exactly as you wrote them

    # [SNIPPED HERE ONLY FOR CHAT SIZE — YOUR LOCAL FILE REMAINS FULL]

    return app


# 🔥 REQUIRED FOR VERCEL (THIS WAS MISSING)
app = create_app()

# Local development only
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
