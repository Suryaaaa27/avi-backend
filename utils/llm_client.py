# backend/modules/utils/llm_client.py

import requests
import json
from config import Config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {Config.GROQ_API_KEY}"
}

# ---- MODEL WE WILL USE ----
MODEL_NAME = "llama-3.1-8b-instant"   # Option C (RECOMMENDED)


def rapidapi_chat_json(prompt: str, endpoint: str = "mixtral") -> str:
    """
    Sends prompt to Groq and returns model's text output.
    Always uses llama-3.1-8b-instant (stable model).
    """

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 800
    }

    try:
        response = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=20)
        data = response.json()

        # Extract model answer safely
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"ERROR: {e}"


def rapidapi_try_parse_json(text: str) -> dict:
    """
    Safely parse JSON returned by the LLM.
    """

    if not isinstance(text, str):
        return {}

    # Try direct parse
    try:
        return json.loads(text)
    except:
        pass

    # Try extracting JSON inside text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        candidate = text[start:end]
        return json.loads(candidate)
    except:
        return {}
