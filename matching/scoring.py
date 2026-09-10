"""
scoring.py — Weighted match scoring engine for FindX.

Computes a final match score (0–100) from component scores using
configurable weights defined in settings.FINDX_MATCH_WEIGHTS.
"""

from datetime import timedelta
from django.conf import settings
from matching.text_matching import semantic_similarity


# ─── Configurable weights (override in settings) ──────────────────────────────
DEFAULT_WEIGHTS = {
    "image":    0.35,
    "text":     0.30,
    "category": 0.10,
    "color":    0.10,
    "location": 0.10,
    "date":     0.05,
}


def get_weights():
    return getattr(settings, "FINDX_MATCH_WEIGHTS", DEFAULT_WEIGHTS)


# ─── Component Scorers ─────────────────────────────────────────────────────────

def score_category(lost, found) -> float:
    """1.0 if same category, 0.0 otherwise."""
    if lost.category_id and found.category_id:
        return 1.0 if lost.category_id == found.category_id else 0.0
    return 0.3  # no category set — neutral


def score_color(lost, found) -> float:
    """Fuzzy colour similarity."""
    def normalise(c):
        return c.lower().strip() if c else ""

    la = normalise(lost.color)
    fb = normalise(found.color)

    if not la or not fb:
        return 0.3  # no colour data — neutral

    if la == fb:
        return 1.0

    # Group common colour families
    FAMILIES = [
        {"black", "dark", "charcoal", "ebony", "jet"},
        {"white", "cream", "ivory", "off-white", "pearl"},
        {"blue", "navy", "royal blue", "sky blue", "cobalt", "denim"},
        {"red", "crimson", "maroon", "scarlet", "cherry"},
        {"green", "olive", "lime", "mint", "forest green", "teal", "cyan"},
        {"yellow", "gold", "amber", "golden", "mustard"},
        {"brown", "tan", "beige", "khaki", "camel", "chocolate"},
        {"gray", "grey", "silver", "ash"},
        {"pink", "rose", "magenta", "fuchsia"},
        {"purple", "violet", "lavender", "indigo"},
        {"orange", "copper", "rust"},
    ]
    for family in FAMILIES:
        if any(c in la for c in family) and any(c in fb for c in family):
            return 0.75

    return 0.0


def score_location(lost, found) -> float:
    """Score based on city / country proximity."""
    def normalise(s):
        return (s or "").lower().strip()

    lc = normalise(lost.city)
    fc = normalise(found.city)
    lco = normalise(lost.country)
    fco = normalise(found.country)

    if lc and fc and lc == fc:
        return 1.0
    if lco and fco and lco == fco:
        return 0.4
    return 0.1


def score_date(lost, found) -> float:
    """
    Score based on how close the event dates are.
    A lost item that was found on the same or adjacent days scores highest.
    """
    if not lost.date_event or not found.date_event:
        return 0.3

    diff = abs((found.date_event - lost.date_event).days)

    if diff <= 1:    return 1.0
    if diff <= 3:    return 0.9
    if diff <= 7:    return 0.75
    if diff <= 14:   return 0.55
    if diff <= 30:   return 0.35
    return 0.1


def score_text(lost, found) -> float:
    """Semantic similarity between the two descriptions."""
    text_a = f"{lost.title} {lost.description} {lost.brand} {lost.color}"
    text_b = f"{found.title} {found.description} {found.brand} {found.color}"
    return semantic_similarity(text_a, text_b)


def score_image(lost, found) -> float:
    """
    Image similarity using stored embeddings.
    Returns 0.0 if either item has no embedding.
    """
    vec_a = lost.get_embedding()
    vec_b = found.get_embedding()

    if not vec_a or not vec_b:
        return 0.0

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        a = np.array(vec_a).reshape(1, -1)
        b = np.array(vec_b).reshape(1, -1)
        sim = cosine_similarity(a, b)[0][0]
        return float(max(0.0, min(1.0, sim)))
    except Exception:
        return 0.0


# ─── Combined Score ────────────────────────────────────────────────────────────

def compute_match_score(lost, found) -> dict:
    """
    Compute all component scores and a weighted final score.

    Returns a dict with keys:
        image_score, text_score, category_score, color_score,
        location_score, date_score, final_score (0–100)
    """
    weights = get_weights()

    components = {
        "image_score":    score_image(lost, found),
        "text_score":     score_text(lost, found),
        "category_score": score_category(lost, found),
        "color_score":    score_color(lost, found),
        "location_score": score_location(lost, found),
        "date_score":     score_date(lost, found),
    }

    final = (
        components["image_score"]    * weights.get("image", 0.35) +
        components["text_score"]     * weights.get("text",  0.30) +
        components["category_score"] * weights.get("category", 0.10) +
        components["color_score"]    * weights.get("color", 0.10) +
        components["location_score"] * weights.get("location", 0.10) +
        components["date_score"]     * weights.get("date", 0.05)
    )

    components["final_score"] = round(final * 100, 2)
    return components
