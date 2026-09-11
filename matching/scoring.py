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
    """
    Semantic similarity between the two descriptions.
    Uses precomputed text embeddings when available for sub-millisecond execution.
    """
    vec_a = lost.get_embedding()
    vec_b = found.get_embedding()

    if vec_a and vec_b:
        from matching.text_matching import vector_cosine_similarity, _keyword_similarity
        sem_sim = vector_cosine_similarity(vec_a, vec_b)
        text_a = f"{lost.title} {lost.description} {lost.brand} {lost.color}"
        text_b = f"{found.title} {found.description} {found.brand} {found.color}"
        kw_sim = _keyword_similarity(text_a, text_b)
        blended = (sem_sim * 0.75) + (kw_sim * 0.25)
        return float(round(max(0.0, min(1.0, blended)), 4))

    text_a = f"{lost.title} {lost.description} {lost.brand} {lost.color}"
    text_b = f"{found.title} {found.description} {found.brand} {found.color}"
    return semantic_similarity(text_a, text_b)


def score_image(lost, found) -> float:
    """
    Real Visual AI image similarity using spatial features, color distributions, and perceptual hashing.
    Returns visual similarity in [0.0, 1.0] if both items have images, or 0.0 if not available.
    """
    has_a = bool(lost.image and str(lost.image).strip())
    has_b = bool(found.image and str(found.image).strip())

    if not has_a or not has_b:
        return 0.0

    try:
        from matching.image_matching import calculate_image_similarity
        return calculate_image_similarity(lost.image, found.image)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Image scoring error: {e}")
        return 0.0


# ─── Combined Score ────────────────────────────────────────────────────────────

def compute_match_score(lost, found) -> dict:
    """
    Compute all component scores and an adaptively weighted final score (0–100).
    
    If both items have images:
        Uses full weights (35% image, 30% text, 10% category, 10% color, 10% location, 5% date).
    If either or both items lack images:
        Dynamically redistributes the image weight proportionally among the other
        active signals so text, category, color, location, and date can fairly
        achieve high match confidence (>= 80-95%) without unfair photo penalties.
    """
    has_images = bool(
        lost.image and str(lost.image).strip() and
        found.image and str(found.image).strip()
    )

    img_score = score_image(lost, found) if has_images else 0.0
    txt_score = score_text(lost, found)
    cat_score = score_category(lost, found)
    clr_score = score_color(lost, found)
    loc_score = score_location(lost, found)
    dat_score = score_date(lost, found)

    components = {
        "image_score":    img_score,
        "text_score":     txt_score,
        "category_score": cat_score,
        "color_score":    clr_score,
        "location_score": loc_score,
        "date_score":     dat_score,
    }

    if has_images:
        # Standard weights (Total = 1.0)
        weights = get_weights()
        final = (
            img_score * weights.get("image",    0.35) +
            txt_score * weights.get("text",     0.30) +
            cat_score * weights.get("category", 0.10) +
            clr_score * weights.get("color",    0.10) +
            loc_score * weights.get("location", 0.10) +
            dat_score * weights.get("date",     0.05)
        )
    else:
        # Adaptive weights when images are not uploaded (Total = 1.0)
        final = (
            txt_score * 0.46 +
            cat_score * 0.15 +
            clr_score * 0.15 +
            loc_score * 0.15 +
            dat_score * 0.09
        )

    components["final_score"] = round(final * 100, 2)
    return components
