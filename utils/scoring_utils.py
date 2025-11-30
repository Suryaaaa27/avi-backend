# backend/utils/scoring_utils.py
import numpy as np

def normalize_score(score, min_val=0, max_val=100):
    """
    Normalizes a score to a 0–1 range.
    """
    return (score - min_val) / (max_val - min_val)


def weighted_average(scores, weights):
    """
    Computes a weighted average of scores from multiple modalities.
    Example:
        scores = {'nlp': 0.8, 'tone': 0.7, 'emotion': 0.9}
        weights = {'nlp': 0.5, 'tone': 0.3, 'emotion': 0.2}
    """
    total_weight = sum(weights.values())
    final_score = sum(scores[k] * weights.get(k, 0) for k in scores) / total_weight
    return round(final_score, 3)


def qualitative_feedback(final_score):
    """
    Maps a numerical score (0–1) to qualitative feedback.
    """
    if final_score >= 0.85:
        return "Excellent"
    elif final_score >= 0.7:
        return "Good"
    elif final_score >= 0.5:
        return "Average"
    else:
        return "Needs Improvement"
