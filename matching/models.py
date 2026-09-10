from django.db import models
from items.models import Item


class Match(models.Model):
    """
    Represents a potential match between a LOST item and a FOUND item.
    Created automatically by the matching engine.
    """
    STATUS_DETECTED      = "DETECTED"
    STATUS_NOTIFIED      = "NOTIFIED"
    STATUS_CLAIMED       = "CLAIMED"
    STATUS_UNDER_REVIEW  = "UNDER_REVIEW"
    STATUS_ACCEPTED      = "ACCEPTED"
    STATUS_REJECTED      = "REJECTED"
    STATUS_RETURNED      = "RETURNED"
    STATUS_CHOICES = (
        (STATUS_DETECTED,     "Detected"),
        (STATUS_NOTIFIED,     "User Notified"),
        (STATUS_CLAIMED,      "Claim Submitted"),
        (STATUS_UNDER_REVIEW, "Under Verification"),
        (STATUS_ACCEPTED,     "Claim Accepted"),
        (STATUS_REJECTED,     "Claim Rejected"),
        (STATUS_RETURNED,     "Item Returned"),
    )

    lost_item  = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="matches_as_lost")
    found_item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="matches_as_found")

    # Component scores (0.0 – 1.0)
    image_score    = models.FloatField(default=0.0)
    text_score     = models.FloatField(default=0.0)
    category_score = models.FloatField(default=0.0)
    color_score    = models.FloatField(default=0.0)
    location_score = models.FloatField(default=0.0)
    date_score     = models.FloatField(default=0.0)

    # Weighted final (0.0 – 100.0)
    final_score = models.FloatField(default=0.0)

    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DETECTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-final_score"]
        unique_together = ("lost_item", "found_item")

    def __str__(self):
        return f"Match {self.final_score:.1f}% — [{self.lost_item.title}] ↔ [{self.found_item.title}]"

    @property
    def strength_label(self):
        if self.final_score >= 85:
            return ("Very Strong", "text-emerald-600", "🟢")
        elif self.final_score >= 70:
            return ("Strong", "text-blue-600", "🔵")
        elif self.final_score >= 55:
            return ("Possible", "text-amber-600", "🟡")
        else:
            return ("Weak", "text-gray-500", "⚪")

    @property
    def strength_color(self):
        if self.final_score >= 85:
            return "#059669"
        elif self.final_score >= 70:
            return "#2563eb"
        elif self.final_score >= 55:
            return "#d97706"
        return "#6b7280"
