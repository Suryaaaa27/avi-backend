# backend/app.py

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
    RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "llama-ai-mixtral-cohere-gpt-api.p.rapidapi.com")
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")  # *** set this in your .env ***
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

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_collection():
        """Get Mongo collection 'interviews' with safe import path."""
        try:
            from backend.database.db_connection import get_collection
        except ImportError:
            from database.db_connection import get_collection
        return get_collection("interviews")

    def _domain_file(domain: str) -> str:
        """Resolve backend/data/<domain>.json (lowercase)."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "data", f"{domain.lower()}.json")

    def _load_questions(domain: str):
        """Load and normalize questions for a domain."""
        fp = _domain_file(domain)
        if not os.path.exists(fp):
            raise FileNotFoundError(f"Questions file not found for domain '{domain}': {fp}")
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "questions" in data:
            raw = data["questions"]
        elif isinstance(data, list):
            raw = data
        else:
            raise ValueError("Invalid questions JSON format. Expected list or { 'questions': [...] }")

        norm = []
        for idx, q in enumerate(raw):
            item = dict(q)
            item["id"] = item.get("id") or f"q{idx+1}"
            item["text"] = item.get("text") or item.get("question") or ""
            item["ideal_answer"] = item.get("ideal_answer") or item.get("answer") or ""
            norm.append(item)
        return norm

    def _numpy_safe(obj: Any) -> Any:
        """Recursively convert numpy numbers to python native types so jsonify works."""
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
        """
        Call RapidAPI Mixtral chat endpoint and return text content.
        """
        if not RAPIDAPI_KEY:
            raise RuntimeError("RAPIDAPI_KEY is not set in environment variables")

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

        logger.debug("RapidAPI request to %s (prompt len=%d)", url, len(prompt))
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)

        try:
            r.raise_for_status()
        except requests.HTTPError as he:
            logger.exception("RapidAPI HTTP error")
            raise RuntimeError(f"RapidAPI HTTP error: {r.status_code} - {r.text}") from he

        try:
            resp_json = r.json()
        except Exception as e:
            logger.exception("Failed to parse RapidAPI JSON response")
            raise RuntimeError("Failed to parse RapidAPI response JSON") from e

        text = None

        # 1) messages
        if isinstance(resp_json.get("messages"), list) and len(resp_json["messages"]):
            m = resp_json["messages"][-1]
            text = m.get("content") or m.get("message")

        # 2) choices
        if text is None and "choices" in resp_json and isinstance(resp_json["choices"], list) and resp_json["choices"]:
            choice = resp_json["choices"][0]
            if isinstance(choice.get("message"), dict):
                text = choice["message"].get("content") or choice["message"].get("text")
            text = text or choice.get("text")

        # 3) direct fields
        if text is None:
            for key in ("response", "text", "result"):
                if isinstance(resp_json.get(key), str):
                    text = resp_json[key]
                    break

        if text is None:
            text = json.dumps(resp_json)

        logger.debug("RapidAPI returned text len=%d", len(text) if isinstance(text, str) else 0)
        return text

    def rapidapi_try_parse_json(model_text: str) -> Dict[str, Any]:
        """
        Attempt to parse a model-produced string into JSON.
        """
        try:
            return json.loads(model_text)
        except Exception:
            start = model_text.find("{")
            end = model_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = model_text[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
            raise ValueError("Failed to parse model response as JSON")

    # =============================
    # Health / Root
    # =============================
    @app.route("/")
    def home():
        return jsonify(
            {
                "message": "🚀 AVI Backend running",
                "debug": app.config.get("DEBUG", False),
            }
        ), 200

    @app.route("/health")
    def health():
        return jsonify({"ok": True}), 200

    # =============================
    # Questions: get next by progress
    # =============================
    @app.route("/question", methods=["GET"])
    def get_next_question():
        """
        Strong-safe:
        - Always returns 200 on success path.
        - current_question is advanced HERE (once per question).
        - /generate-feedback no longer increments index.
        """
        email = (request.args.get("email") or "").strip().lower()
        interview_id = (request.args.get("interview_id") or "").strip()
        domain = (request.args.get("domain") or "").strip().lower()

        if not email or not interview_id or not domain:
            return jsonify({"success": False, "error": "email, interview_id, domain are required"}), 400

        try:
            qs = _load_questions(domain)
            total = len(qs)

            if total == 0:
                return jsonify({"success": False, "error": "No questions in this domain"}), 400

            col = _get_collection()
            key = {"email": email, "interview_id": interview_id, "domain": domain}

            doc = col.find_one(key)
            if not doc:
                doc = {**key, "current_question": 0, "results": []}
                col.insert_one(doc)

            idx = int(doc.get("current_question", 0))

            # All questions served → done
            if idx >= total:
                return jsonify({"success": True, "done": True, "total": total}), 200

            # Fetch current question
            q = qs[idx]

            # IMPORTANT:
            # Advance index here for next time.
            col.update_one(key, {"$set": {"current_question": idx + 1}}, upsert=True)

            return jsonify(
                {
                    "success": True,
                    "done": False,
                    "index": idx + 1,   # 1-based for UI
                    "total": total,
                    "id": q["id"],
                    "text": q["text"],
                    "ideal_answer_hint": None,
                }
            ), 200

        except Exception as e:
            logger.exception("get_next_question failed")
            return jsonify({"success": False, "error": str(e)}), 500

    # =============================
    # Progress reset
    # =============================
    @app.route("/progress/reset", methods=["POST"])
    def reset_progress():
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        interview_id = (data.get("interview_id") or "").strip()
        domain = (data.get("domain") or "").strip().lower()

        if not email or not interview_id or not domain:
            return jsonify({"success": False, "error": "email, interview_id, domain are required"}), 400

        try:
            col = _get_collection()
            key = {"email": email, "interview_id": interview_id, "domain": domain}
            col.update_one(
                key,
                {"$set": {"current_question": 0, "results": []}},
                upsert=True,
            )
            return jsonify({"success": True, "current_question": 0}), 200
        except Exception as e:
            logger.exception("reset_progress failed")
            return jsonify({"success": False, "error": str(e)}), 500

    # =============================
    # Transcribe (strong safe)
    # =============================
    @app.route("/transcribe", methods=["POST"])
    def transcribe():
        """
        Strong-safe: always returns 200.
        If anything fails, returns success=False and empty text,
        but NEVER breaks the frontend pipeline.
        """
        try:
            if "audio" not in request.files:
                return (
                    jsonify(
                        {
                            "success": False,
                            "text": "",
                            "language": "",
                            "error": "No audio file provided",
                        }
                    ),
                    200,
                )

            audio_file = request.files["audio"]
            result = transcribe_audio(audio_file)

            if not result.get("success"):
                return (
                    jsonify(
                        {
                            "success": False,
                            "text": "",
                            "language": "",
                            "error": result.get("error", "transcription failed"),
                        }
                    ),
                    200,
                )

            return (
                jsonify(
                    {
                        "success": True,
                        "text": (result.get("text") or "").strip(),
                        "language": result.get("language", "unknown"),
                    }
                ),
                200,
            )
        except Exception as e:
            logger.exception("transcribe error")
            return (
                jsonify(
                    {
                        "success": False,
                        "text": "",
                        "language": "",
                        "error": str(e),
                    }
                ),
                200,
            )

    # =============================
    # Generic NLP Similarity
    # =============================
    @app.route("/evaluate", methods=["POST"])
    def evaluate():
        try:
            data = request.get_json() or {}
            user_response = (data.get("user_response") or "").strip()
            reference_text = (data.get("reference_text") or "").strip()
            result = evaluate_text(user_response, reference_text)
            return jsonify({"success": True, "evaluation": _numpy_safe(result)}), 200
        except Exception as e:
            logger.exception("evaluate failed")
            return jsonify({"success": False, "error": str(e)}), 500

    # =============================
    # Domain NLP (strong safe)
    # =============================
    @app.route("/evaluate_domain", methods=["POST"])
    def evaluate_domain_route():
        """
        Strong-safe:
        - Always returns 200.
        - If all evaluators fail, returns a neutral 50% score + generic feedback.
        """
        try:
            data = request.get_json() or {}
            domain = (data.get("domain") or "").strip().lower()
            user_response = (data.get("user_response") or "").strip()
            question_id = (data.get("question_id") or "").strip()
            question_text = (data.get("question_text") or "").strip()
            custom_reference = (data.get("reference_answer") or "").strip()

            if not domain:
                return jsonify({"success": False, "error": "domain is required"}), 400

            qs = _load_questions(domain)

            # Determine ideal answer
            ideal_answer = None
            if custom_reference:
                ideal_answer = custom_reference
            else:
                match = None
                if question_id:
                    match = next((q for q in qs if q["id"] == question_id), None)
                elif question_text:
                    match = next((q for q in qs if q["text"] == question_text), None)
                if match:
                    ideal_answer = match.get("ideal_answer") or ""

            if ideal_answer is None:
                ideal_answer = ""

            # 1) Try your domain_evaluator
            try:
                logger.debug("Calling evaluate_domain_response (primary)...")
                r = evaluate_domain_response(user_response, ideal_answer)
                r = _numpy_safe(r)
                logger.debug("Domain evaluator returned: %s", r)
                return jsonify({"success": True, "evaluation": r}), 200
            except Exception:
                logger.exception("domain_evaluator failed, falling back to TF-IDF local scorer")

            # 2) TF-IDF fallback
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity

                vec = TfidfVectorizer(stop_words="english").fit_transform(
                    [user_response or "", ideal_answer or ""]
                )
                if vec.shape[0] < 2:
                    score_pct = 0.0
                else:
                    sim = float(cosine_similarity(vec[0], vec[1])[0][0])
                    score_pct = round(sim * 100.0, 2)

                feedback = (
                    "Excellent answer!" if score_pct > 80 else
                    "Good attempt!" if score_pct > 60 else
                    "Fair answer — try to include more key points." if score_pct > 40 else
                    "Weak match — revise the core concept and try again."
                )

                fallback = {"similarity_score": score_pct, "feedback": feedback}
                logger.debug("Fallback TF-IDF result: %s", fallback)
                return jsonify({"success": True, "evaluation": fallback}), 200
            except Exception:
                logger.exception("Fallback TF-IDF also failed; attempting RapidAPI fallback")

            # 3) RapidAPI Mixtral fallback
            try:
                prompt = f"""
You are an expert evaluation assistant. Compare the USER ANSWER to the IDEAL ANSWER and
return JSON ONLY in the format:
{{"similarity_score": <0-100>,"feedback":"short constructive feedback"}}

USER ANSWER:
{user_response}

IDEAL ANSWER:
{ideal_answer}
"""
                model_text = rapidapi_chat_json(prompt, endpoint="mixtral")
                parsed = rapidapi_try_parse_json(model_text)
                parsed_out = {
                    "similarity_score": float(parsed.get("similarity_score", parsed.get("score", 50))),
                    "feedback": parsed.get("feedback", parsed.get("comment", "")),
                }
                return jsonify({"success": True, "evaluation": _numpy_safe(parsed_out)}), 200
            except Exception as e:
                logger.exception("RapidAPI fallback failed in evaluate_domain")

            # 4) Last-resort safe default
            safe_default = {
                "similarity_score": 50.0,
                "feedback": "We could not fully evaluate this answer due to a system issue, "
                            "but you can still review your response and try again.",
            }
            return jsonify({"success": True, "evaluation": safe_default}), 200

        except Exception as e:
            logger.exception("evaluate_domain_route failed (hard)")
            safe_default = {
                "similarity_score": 50.0,
                "feedback": "We could not fully evaluate this answer due to a system error.",
            }
            return jsonify({"success": True, "evaluation": safe_default, "warning": str(e)}), 200

    # =============================
    # Vision + Audio routes (strong safe)
    # =============================
    @app.route("/detect-emotion", methods=["POST"])
    def detect_emotion_route():
        """
        Strong-safe:
        - Always returns 200.
        - On failure, returns neutral emotion + success=False.
        """
        try:
            if "image" not in request.files:
                return (
                    jsonify(
                        {
                            "success": False,
                            "dominant_emotion": "neutral",
                            "emotion_scores": {"neutral": 1.0},
                            "error": "No image file provided",
                        }
                    ),
                    200,
                )

            image_file = request.files["image"]
            result = detect_emotion(image_file) or {}
            result.setdefault("success", True)
            return jsonify(_numpy_safe(result)), 200
        except Exception as e:
            logger.exception("detect_emotion failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "dominant_emotion": "neutral",
                        "emotion_scores": {"neutral": 1.0},
                        "error": str(e),
                    }
                ),
                200,
            )

    @app.route("/analyze-posture", methods=["POST"])
    def analyze_posture_route():
        """
        Strong-safe:
        - Always returns 200.
        - On failure, returns summary saying posture not detected.
        """
        try:
            if "video" not in request.files:
                return (
                    jsonify(
                        {
                            "success": False,
                            "summary": "Posture not detected (no video).",
                            "error": "No video file provided",
                        }
                    ),
                    200,
                )

            video_file = request.files["video"]
            result = analyze_posture(video_file) or {}
            result.setdefault("success", True)
            return jsonify(_numpy_safe(result)), 200
        except Exception as e:
            logger.exception("analyze_posture failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "summary": "Posture not detected (processing error).",
                        "error": str(e),
                    }
                ),
                200,
            )

    @app.route("/analyze-tone", methods=["POST"])
    def analyze_tone_route():
        """
        Strong-safe:
        - Always returns 200.
        - On failure, returns neutral-ish tone result.
        """
        try:
            if "audio" not in request.files:
                return (
                    jsonify(
                        {
                            "success": False,
                            "detected_emotion": "neutral",
                            "emotion_scores": {"neu": 1.0},
                            "energy": 0.05,
                            "pitch": 0.0,
                            "error": "No audio file provided",
                        }
                    ),
                    200,
                )

            audio_file = request.files["audio"]
            result = analyze_tone(audio_file) or {}
            result.setdefault("success", True)
            return jsonify(_numpy_safe(result)), 200
        except Exception as e:
            logger.exception("analyze_tone failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "detected_emotion": "neutral",
                        "emotion_scores": {"neu": 1.0},
                        "energy": 0.05,
                        "pitch": 0.0,
                        "error": str(e),
                    }
                ),
                200,
            )

    # =============================
    # Final feedback (persist)
    # =============================
    @app.route("/generate-feedback", methods=["POST"])
    def generate_feedback_route():
        """
        Strong-safe:
        - ALWAYS returns 200.
        - Never breaks the frontend with 500.
        - If generator or RapidAPI fail, falls back to a basic but valid feedback block.
        - DOES NOT increment current_question (that is handled in /question).
        """
        try:
            data = request.get_json() or {}
            email = (data.get("email") or "").strip().lower()
            interview_id = (data.get("interview_id") or "").strip()
            domain = (data.get("domain") or "").strip().lower()

            # Normalize NLP result shape
            nlp_result_raw = data.get("nlp_result", {}) or {}
            if "score" in nlp_result_raw and "similarity_score" not in nlp_result_raw:
                nlp_result = {
                    "similarity_score": nlp_result_raw["score"],
                    "feedback": nlp_result_raw.get("feedback", ""),
                }
            else:
                nlp_result = nlp_result_raw

            emotion_result = data.get("emotion_result", {}) or {}
            posture_result = data.get("posture_result", {}) or {}
            tone_result = data.get("tone_result", {}) or {}
            question_meta = data.get("question_meta", {}) or {}

            # ---- Try local feedback_generator first
            try:
                result = generate_feedback(
                    nlp_result,
                    emotion_result,
                    posture_result,
                    tone_result,
                    email=email,
                    interview_id=interview_id,
                )
            except Exception:
                logger.exception("generate_feedback (local) failed - trying RapidAPI Mixtral fallback")

                prompt = f"""
You are an expert senior interviewer and HR evaluator. Using the signals below, produce JSON output ONLY with three fields:
{{ "final_score": <0-1 float>, "qualitative_rating": "<Excellent|Good|Average|Poor>", "feedback": "<detailed multi-paragraph feedback>" }}

NLP EVALUATION:
{json.dumps(_numpy_safe(nlp_result), ensure_ascii=False, indent=2)}

EMOTION:
{json.dumps(_numpy_safe(emotion_result), ensure_ascii=False, indent=2)}

POSTURE:
{json.dumps(_numpy_safe(posture_result), ensure_ascii=False, indent=2)}

TONE:
{json.dumps(_numpy_safe(tone_result), ensure_ascii=False, indent=2)}

Be professional, concise, and output valid JSON only.
"""
                try:
                    model_text = rapidapi_chat_json(prompt, endpoint="mixtral")
                    parsed = rapidapi_try_parse_json(model_text)

                    result = {
                        "final_score": float(parsed.get("final_score", parsed.get("score", 0.5))),
                        "qualitative_rating": parsed.get(
                            "qualitative_rating", parsed.get("rating", "Average")
                        ),
                        "feedback": parsed.get(
                            "feedback", parsed.get("comment", str(parsed))
                        ),
                    }
                except Exception:
                    logger.exception("RapidAPI Mixtral fallback failed for generate_feedback")

                    # Last-resort basic aggregation
                    agg_score = 0.5
                    try:
                        if isinstance(nlp_result, dict) and (
                            "similarity_score" in nlp_result or "score" in nlp_result
                        ):
                            s = nlp_result.get("similarity_score", nlp_result.get("score"))
                            if s is not None:
                                s = float(s)
                                agg_score = s / 100.0 if s > 1.0 else s
                    except Exception:
                        agg_score = 0.5

                    qualitative = (
                        "Excellent"
                        if agg_score >= 0.8
                        else "Good"
                        if agg_score >= 0.65
                        else "Average"
                        if agg_score >= 0.45
                        else "Poor"
                    )

                    result = {
                        "final_score": agg_score,
                        "qualitative_rating": qualitative,
                        "feedback": (
                            "We could not generate a detailed AI explanation right now, "
                            "but based on your answer similarity, this is your approximate rating. "
                            "Try to expand your answers with more structure and examples."
                        ),
                    }

            # ---- Persist per-question result (no index increment here)
            if email and interview_id and domain:
                try:
                    col = _get_collection()
                    key = {"email": email, "interview_id": interview_id, "domain": domain}

                    per_q = {
                        "question_id": question_meta.get("id"),
                        "question_text": question_meta.get("text"),
                        "question_index": question_meta.get("index"),
                        "nlp_result": nlp_result,
                        "emotion_result": emotion_result,
                        "posture_result": posture_result,
                        "tone_result": tone_result,
                        "final_score": result.get("final_score"),
                        "qualitative_rating": result.get("qualitative_rating"),
                        "feedback": result.get("feedback"),
                    }

                    # Ensure doc exists
                    col.update_one(
                        key,
                        {"$setOnInsert": {"results": []}},
                        upsert=True,
                    )
                    # Push result only (NO $inc here)
                    col.update_one(
                        key,
                        {"$push": {"results": per_q}},
                        upsert=False,
                    )
                except Exception:
                    logger.exception("persist per-question result failed (nonfatal)")

            return (
                jsonify(
                    {
                        "success": True,
                        "feedback": result.get("feedback"),
                        "final_score": result.get("final_score"),
                        "qualitative_rating": result.get("qualitative_rating"),
                        "email": email,
                        "interview_id": interview_id,
                        "domain": domain,
                    }
                ),
                200,
            )

        except Exception as e:
            logger.exception("generate_feedback failed (outer)")
            # Very last-resort safe response
            fallback = {
                "final_score": 0.5,
                "qualitative_rating": "Average",
                "feedback": (
                    "We could not generate a detailed analysis due to a system error, "
                    "but your attempt has been recorded. Try to keep answers structured "
                    "and add examples where possible."
                ),
            }
            return (
                jsonify(
                    {
                        "success": True,
                        "feedback": fallback["feedback"],
                        "final_score": fallback["final_score"],
                        "qualitative_rating": fallback["qualitative_rating"],
                        "error": str(e),
                    }
                ),
                200,
            )

    # =============================
    # Final feedback fetch for dashboard
    # =============================
    @app.route("/final_feedback", methods=["GET"])
    def final_feedback():
        email = (request.args.get("email") or "").strip().lower()
        interview_id = (request.args.get("interview_id") or "").strip()

        if not email or not interview_id:
            return jsonify({"success": False, "error": "email & interview_id required"}), 400

        col = _get_collection()
        doc = col.find_one({"email": email, "interview_id": interview_id})

        if not doc:
            return jsonify({"success": False, "error": "not found"}), 404

        last_list = doc.get("results", [])
        last = last_list[-1] if last_list else {}

        return jsonify(
            {
                "success": True,
                "final_score": last.get("final_score"),
                "qualitative_rating": last.get("qualitative_rating"),
                "nlp_result": last.get("nlp_result"),
                "emotion_result": last.get("emotion_result"),
                "posture_result": last.get("posture_result"),
                "tone_result": last.get("tone_result"),
                "feedback": last.get("feedback"),
            }
        ), 200

    return app


# =============================
# 🚀 Run the Application
# =============================
if __name__ == "__main__":
    print("[DEBUG] starting app create")
    application = create_app()
    print("[DEBUG] starting flask")
    application.run(host="0.0.0.0", port=5000, debug=True)
