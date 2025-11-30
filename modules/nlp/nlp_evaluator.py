# backend/modules/nlp/nlp_evaluator.py

import os
os.environ["TRANSFORMERS_NO_TORCHVISION"] = "1"
os.environ["TRANSFORMERS_NO_TORCHVISION_IMPORT_ERROR"] = "1"
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str, model="text-embedding-3-small"):
    """
    Generate an embedding vector for a given text.
    """
    if not text or text.strip() == "":
        return np.zeros((1, 1536))  # fallback zero-vector

    response = client.embeddings.create(
        input=text,
        model=model
    )
    return np.array(response.data[0].embedding).reshape(1, -1)


def semantic_similarity(text1: str, text2: str) -> float:
    """
    Compute cosine similarity between two texts using embeddings.
    Returns a similarity score between 0 and 1.
    """
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)

    similarity = cosine_similarity(emb1, emb2)[0][0]
    return float(similarity)


def evaluate_text(user_response: str, reference_text: str) -> dict:
    """
    Compare user's response with the reference text and return an evaluation dictionary.
    """
    similarity_score = semantic_similarity(user_response, reference_text)
    percentage = round(similarity_score * 100, 2)

    if percentage > 80:
        feedback = "Excellent! You understood the concept clearly."
    elif percentage > 60:
        feedback = "Good attempt! You’re on the right track."
    elif percentage > 40:
        feedback = "Fair effort, but try to be more precise."
    else:
        feedback = "Needs improvement. Review the topic again."

    return {
        "user_response": user_response,
        "reference_text": reference_text,
        "similarity_score": percentage,
        "feedback": feedback
    }

# For quick local test
if __name__ == "__main__":
    result = evaluate_text(
        "Artificial Intelligence is about simulating human intelligence.",
        "AI refers to machines that mimic human intelligence processes."
    )
    print(result)
