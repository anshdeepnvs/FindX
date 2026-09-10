"""
text_matching.py — Semantic text similarity for FindX matching engine.

Uses sentence-transformers (all-MiniLM-L6-v2) when available.
Falls back to keyword overlap (Jaccard similarity) automatically.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ─── Sentence Transformers (loaded lazily on first use) ────────────────────────
_model = None
_model_load_attempted = False


def _get_model():
    """Lazy-load the sentence transformer model. Returns None on failure."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from django.conf import settings
        if not getattr(settings, "FINDX_USE_SENTENCE_TRANSFORMERS", True):
            logger.info("Sentence transformers disabled in settings — using keyword fallback.")
            return None
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)…")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence-transformers model loaded successfully.")
    except Exception as e:
        logger.warning(f"Could not load sentence-transformers model: {e}. Using keyword fallback.")
        _model = None
    return _model


def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Return cosine similarity in [0.0, 1.0] between two text strings.
    Uses sentence-transformers if available; keyword Jaccard otherwise.
    """
    if not text_a or not text_b:
        return 0.0

    model = _get_model()
    if model is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            embeddings = model.encode([text_a, text_b], convert_to_numpy=True)
            sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(max(0.0, min(1.0, sim)))
        except Exception as e:
            logger.warning(f"Sentence transformer inference failed: {e}. Using fallback.")

    return _keyword_similarity(text_a, text_b)


def _keyword_similarity(text_a: str, text_b: str) -> float:
    """
    Simple keyword-overlap similarity.
    Tokenises, removes stopwords, returns Jaccard coefficient.
    """
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "it", "is", "was", "i", "my", "this", "that", "has",
        "have", "had", "its", "are", "be", "been", "very", "some", "any",
        "from", "by", "not", "no", "so", "do", "did",
    }

    def tokenise(text):
        tokens = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
        return set(t for t in tokens if t not in STOPWORDS and len(t) > 2)

    set_a = tokenise(text_a)
    set_b = tokenise(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def get_text_embedding(text: str):
    """Return a numpy embedding for a string, or None if model unavailable."""
    model = _get_model()
    if model is None:
        return None
    try:
        return model.encode(text, convert_to_numpy=True)
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None
