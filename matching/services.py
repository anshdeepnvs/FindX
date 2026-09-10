"""
services.py — Orchestrates the FindX matching pipeline.

Called via Django signal (post_save on Item) and from management commands.
"""

import logging
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def run_matching(item):
    """
    Given a newly saved Item, find all potential matches from the opposite type.
    Creates or updates Match records. Returns the number of matches stored.
    """
    from items.models import Item
    from matching.models import Match
    from matching.scoring import compute_match_score
    from matching.text_matching import get_text_embedding
    from notifications.utils import notify_user

    thresholds = getattr(settings, "FINDX_MATCH_THRESHOLDS", {})
    min_score  = thresholds.get("minimum", 40)

    # If the item itself is inactive, closed, or already verified, skip matching
    if not item.is_active or item.status not in (Item.STATUS_ACTIVE, Item.STATUS_MATCH_FOUND):
        return 0

    # If this item already has an accepted/resolved match, do not search for new matches
    if item.item_type == Item.TYPE_LOST:
        if item.matches_as_lost.filter(status__in=[Match.STATUS_ACCEPTED, Match.STATUS_RETURNED]).exists():
            return 0
    else:
        if item.matches_as_found.filter(status__in=[Match.STATUS_ACCEPTED, Match.STATUS_RETURNED]).exists():
            return 0

    # Determine opposite type and filter ONLY active, unverified items
    opposite_type = Item.TYPE_FOUND if item.item_type == Item.TYPE_LOST else Item.TYPE_LOST
    candidates = Item.objects.filter(
        item_type=opposite_type,
        is_active=True,
        status__in=[Item.STATUS_ACTIVE, Item.STATUS_MATCH_FOUND],
    ).exclude(
        reporter=item.reporter
    ).exclude(
        matches_as_lost__status__in=[Match.STATUS_ACCEPTED, Match.STATUS_RETURNED]
    ).exclude(
        matches_as_found__status__in=[Match.STATUS_ACCEPTED, Match.STATUS_RETURNED]
    )

    # Ensure item has a text embedding stored
    _ensure_embedding(item)

    count = 0
    for candidate in candidates:
        _ensure_embedding(candidate)

        scores = compute_match_score(
            lost=item  if item.item_type == Item.TYPE_LOST else candidate,
            found=candidate if item.item_type == Item.TYPE_LOST else item,
        )

        final = scores["final_score"]
        if final < min_score:
            continue

        lost_item  = item      if item.item_type == Item.TYPE_LOST else candidate
        found_item = candidate if item.item_type == Item.TYPE_LOST else item

        with transaction.atomic():
            match, created = Match.objects.update_or_create(
                lost_item=lost_item,
                found_item=found_item,
                defaults={
                    "image_score":    scores["image_score"],
                    "text_score":     scores["text_score"],
                    "category_score": scores["category_score"],
                    "color_score":    scores["color_score"],
                    "location_score": scores["location_score"],
                    "date_score":     scores["date_score"],
                    "final_score":    final,
                },
            )

            if created or match.status == Match.STATUS_DETECTED:
                match.status = Match.STATUS_NOTIFIED
                match.save(update_fields=["status"])

                # De-duplicate: Never send duplicate notification for the same match
                from notifications.models import Notification
                match_link = f"/matching/{match.id}/"
                if not Notification.objects.filter(user=lost_item.reporter, notif_type="MATCH", link=match_link).exists():
                    notify_user(
                        user=lost_item.reporter,
                        notif_type="MATCH",
                        title=f"🔍 Potential match found for '{lost_item.title}'!",
                        body=(
                            f"A found item '{found_item.title}' scored "
                            f"{final:.0f}% similarity with your lost item."
                        ),
                        link=match_link,
                    )

        count += 1

    logger.info(f"run_matching({item.id}): {count} match(es) stored/updated.")
    return count


def _ensure_embedding(item):
    """Generate and save a text embedding for item if it doesn't have one."""
    if item.embedding_json:
        return
    from matching.text_matching import get_text_embedding
    text = f"{item.title} {item.description} {item.brand} {item.color}"
    vec = get_text_embedding(text)
    if vec is not None:
        item.set_embedding(vec)
        item.save(update_fields=["embedding_json"])
