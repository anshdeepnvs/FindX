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


import numpy as np

# Cache for recently encoded text strings to avoid repetitive inference
_TEXT_EMBED_CACHE = {}
_MAX_CACHE_SIZE = 500


def vector_cosine_similarity(vec_a, vec_b) -> float:
    """
    Ultra-fast cosine similarity between two precomputed 1D vectors/lists.
    Executes in < 0.01 milliseconds.
    """
    if not vec_a or not vec_b:
        return 0.0
    try:
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        dot = float(np.dot(a, b) / (norm_a * norm_b))
        return float(max(0.0, min(1.0, dot)))
    except Exception as e:
        logger.warning(f"Vector cosine similarity error: {e}")
        return 0.0


def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Return cosine similarity in [0.0, 1.0] between two text strings.
    Uses sentence-transformers with caching if available; keyword Jaccard otherwise.
    Blends with brand/model token overlap for extra precision.
    """
    if not text_a or not text_b:
        return 0.0

    clean_a = text_a.strip()
    clean_b = text_b.strip()

    if clean_a.lower() == clean_b.lower():
        return 1.0

    # 1. Semantic Embedding Similarity
    emb_a = get_text_embedding(clean_a)
    emb_b = get_text_embedding(clean_b)

    if emb_a is not None and emb_b is not None:
        sem_sim = vector_cosine_similarity(emb_a, emb_b)
    else:
        sem_sim = _keyword_similarity(clean_a, clean_b)

    # 2. Token & Brand / Number Boost
    kw_sim = _keyword_similarity(clean_a, clean_b)

    # Look for matching numbers or exact brand model terms (e.g. "14", "pro", "wildcraft")
    nums_a = set(re.findall(r"\b\d+\b", clean_a.lower()))
    nums_b = set(re.findall(r"\b\d+\b", clean_b.lower()))
    num_match = bool(nums_a.intersection(nums_b))

    # Balanced composite: 75% semantic + 25% exact keywords
    blended = (sem_sim * 0.75) + (kw_sim * 0.25)
    if num_match:
        blended = min(1.0, blended + 0.08)

    return float(round(max(0.0, min(1.0, blended)), 4))


def _keyword_similarity(text_a: str, text_b: str) -> float:
    """
    Simple keyword-overlap similarity.
    Tokenises, removes stopwords, returns Jaccard coefficient.
    """
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "it", "is", "was", "i", "my", "this", "that", "has",
        "have", "had", "its", "are", "be", "been", "very", "some", "any",
        "from", "by", "not", "no", "so", "do", "did", "please", "lost", "found",
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
    """Return a numpy embedding for a string, using in-memory cache for speed."""
    if not text:
        return None

    global _TEXT_EMBED_CACHE
    cache_key = text.strip().lower()
    if cache_key in _TEXT_EMBED_CACHE:
        return _TEXT_EMBED_CACHE[cache_key]

    model = _get_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, convert_to_numpy=True)
        if len(_TEXT_EMBED_CACHE) < _MAX_CACHE_SIZE:
            _TEXT_EMBED_CACHE[cache_key] = vec
        return vec
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None
