# backend/modules/nlp/domain_evaluator.py

from typing import Dict, Any

from utils.llm_client import (
    rapidapi_chat_json,
    rapidapi_try_parse_json,
)


def evaluate_domain_response(user_response: str,
                             correct_answer: str) -> Dict[str, Any]:
    """
    Domain-specific evaluation for a single answer.

    Primary path: RapidAPI (Mixtral).
    Fallback handled in app.py with TF-IDF.

    Returns:
        {
            "similarity_score": <0-100 float>,
            "feedback": "<2–4 sentences of friendly, constructive feedback>"
        }
    """

    user_response = (user_response or "").strip()
    correct_answer = (correct_answer or "").strip()

    # If literally nothing answered
    if not user_response:
        return {
            "similarity_score": 0.0,
            "feedback": (
                "No response was detected. Try explaining your thoughts next time, "
                "even if you're unsure — 2–3 sentences are enough."
            )
        }

    # -----------------------------
    # LLM Prompt
    # -----------------------------
    prompt = f"""
You are a technical interview evaluator.

Compare the candidate's answer to the IDEAL reference answer.

CANDIDATE ANSWER:
\"\"\"{user_response}\"\"\"

IDEAL ANSWER:
\"\"\"{correct_answer}\"\"\"

Evaluate based on:
- correctness
- relevance
- clarity
- structure
- depth of explanation

Return ONLY VALID JSON (no markdown, no extra text) in this exact format:

{{
  "similarity_score": <0-100>,
  "feedback": "<2–4 sentences of friendly, constructive, actionable feedback>"
}}
"""

    # -----------------------------
    # Call RapidAPI → Mixtral
    # -----------------------------
    try:
        model_text = rapidapi_chat_json(prompt, endpoint="mixtral")
        parsed = rapidapi_try_parse_json(model_text)
    except Exception:
        # If something goes wrong, return safe fallback
        return {
            "similarity_score": 50.0,
            "feedback": (
                "Decent attempt! Try adding more structure and covering the key points "
                "more clearly. Short examples also help improve clarity."
            )
        }

    # -----------------------------
    # Extract Score
    # -----------------------------
    score = parsed.get("similarity_score", parsed.get("score"))
    if score is None:
        score_f = 50.0
    else:
        try:
            score_f = float(score)
        except Exception:
            score_f = 50.0

    # -----------------------------
    # Extract Feedback
    # -----------------------------
    feedback = parsed.get(
        "feedback",
        "Good attempt! Try to cover the main definition and add 1–2 brief examples."
    )

    return {
        "similarity_score": max(0.0, min(100.0, score_f)),
        "feedback": feedback,
    }
