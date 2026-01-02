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

    # ---- CORS
    CORS(
        app,
        resources={r"/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500"]}},
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "OPTIONS"],
        max_age=86400,
    )

    # -----------------------------
    # RapidAPI config
    # -----------------------------
    RAPIDAPI_HOST = os.getenv(
        "RAPIDAPI_HOST",
        "llama-ai-mixtral-cohere-gpt-api.p.rapidapi.com",
    )
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_BASE = f"https://{RAPIDAPI_HOST}"

    # -----------------------------
    # SAFE imports (no CV / OpenAI here)
    # -----------------------------
    from modules.nlp.speech_to_text import transcribe_audio
    from modules.nlp.nlp_evaluator import evaluate_text
    from modules.feedback.feedback_generator import generate_feedback
    from modules.nlp.domain_evaluator import evaluate_domain_response
    from database.db_connection import get_collection

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_collection():
        return get_collection("interviews")

    def _domain_file(domain: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "data", f"{domain.lower()}.json")

    def _load_questions(domain: str):
        fp = _domain_file(domain)
        if not os.path.exists(fp):
            raise FileNotFoundError(f"Questions file not found for domain '{domain}'")

        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw = data["questions"] if isinstance(data, dict) else data

        norm = []
        for idx, q in enumerate(raw):
            item = dict(q)
            item["id"] = item.get("id") or f"q{idx+1}"
            item["text"] = item.get("text") or item.get("question") or ""
            item["ideal_answer"] = item.get("ideal_answer") or item.get("answer") or ""
            norm.append(item)
        return norm

    def _numpy_safe(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _numpy_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_numpy_safe(x) for x in obj]
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        return obj

    def rapidapi_chat_json(prompt: str, endpoint="mixtral", timeout=30):
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
        }

        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json().get("messages", [{}])[-1].get("content", "")

    # =============================
    # ROUTES
    # =============================

    @app.route("/")
    def home():
        return jsonify({"message": "🚀 AVI Backend running"}), 200

    @app.route("/health")
    def health():
        return jsonify({"ok": True}), 200

    @app.route("/question", methods=["GET"])
    def get_next_question():
        email = request.args.get("email", "").lower()
        interview_id = request.args.get("interview_id", "")
        domain = request.args.get("domain", "").lower()

        qs = _load_questions(domain)
        col = _get_collection()
        key = {"email": email, "interview_id": interview_id, "domain": domain}

        doc = col.find_one(key) or {**key, "current_question": 0, "results": []}
        idx = int(doc.get("current_question", 0))

        if idx >= len(qs):
            return jsonify({"success": True, "done": True}), 200

        col.update_one(key, {"$set": {"current_question": idx + 1}}, upsert=True)
        q = qs[idx]

        return jsonify({
            "success": True,
            "id": q["id"],
            "text": q["text"],
            "index": idx + 1,
            "total": len(qs)
        }), 200

    @app.route("/transcribe", methods=["POST"])
    def transcribe():
        audio = request.files.get("audio")
        if not audio:
            return jsonify({"success": False}), 200
        return jsonify(transcribe_audio(audio)), 200

    @app.route("/evaluate", methods=["POST"])
    def evaluate():
        data = request.get_json()
        return jsonify(evaluate_text(data["user_response"], data["reference_text"])), 200

    @app.route("/detect-emotion", methods=["POST"])
    def detect_emotion_route():
        from modules.vision.emotion_detector import detect_emotion
        return jsonify(detect_emotion(request.files["image"])), 200

    @app.route("/analyze-posture", methods=["POST"])
    def analyze_posture_route():
        from modules.vision.posture_tracker import analyze_posture
        return jsonify(analyze_posture(request.files["video"])), 200

    @app.route("/analyze-tone", methods=["POST"])
    def analyze_tone_route():
        from modules.speech.tone_analyzer import analyze_tone
        return jsonify(analyze_tone(request.files["audio"])), 200

    @app.route("/generate-feedback", methods=["POST"])
    def generate_feedback_route():
        data = request.get_json()
        return jsonify(generate_feedback(**data)), 200

    return app
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)


