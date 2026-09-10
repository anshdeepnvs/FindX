from django.db import models
from django.conf import settings
from matching.models import Match


class OwnershipClaim(models.Model):
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_PENDING     = "PENDING"
    STATUS_ACCEPTED    = "ACCEPTED"
    STATUS_REJECTED    = "REJECTED"
    STATUS_CANCELLED   = "CANCELLED"
    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, "AI Verification in Progress"),
        (STATUS_PENDING,     "Pending Review"),
        (STATUS_ACCEPTED,    "Accepted — Proceed to Return"),
        (STATUS_REJECTED,    "Rejected"),
        (STATUS_CANCELLED,   "Cancelled"),
    )

    match     = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="claims")
    claimant  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="ownership_claims")
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Interactive AI interview transcript: [{"role": "assistant"|"user", "content": "...", "timestamp": "..."}]
    interview_history = models.JSONField(default=list, blank=True, help_text="Interactive AI chat interview history")

    # Claimant's free-text answer / consolidated transcript summary
    answer_text    = models.TextField(blank=True, default="", help_text="Claimant's description of private identifying details")
    proof_image    = models.ImageField(upload_to="claim_proofs/", blank=True, null=True,
                                        help_text="Purchase receipt, old photo, ID snippet, etc.")
    additional_info= models.TextField(blank=True)

    # AI Verification Results
    ai_score         = models.FloatField(null=True, blank=True, help_text="AI match score 0-100")
    ai_confidence    = models.CharField(max_length=20, default="PENDING")
    ai_reasoning     = models.TextField(blank=True, help_text="AI reasoning summary")
    is_ai_verified   = models.BooleanField(default=False)

    # Finder's rejection reason (if rejected)
    rejection_reason = models.TextField(blank=True)

    # Handover OTP for physical return verification (generated ONLY after finder verifies)
    finder_verified    = models.BooleanField(default=False)
    finder_verified_at = models.DateTimeField(null=True, blank=True)
    handover_otp       = models.CharField(max_length=6, blank=True, default="")
    is_handover_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("match", "claimant")

    def generate_handover_otp(self):
        import random
        if not self.handover_otp:
            self.handover_otp = f"{random.randint(100000, 999999)}"
            self.save(update_fields=["handover_otp"])
        return self.handover_otp

    def save(self, *args, **kwargs):
        import random
        # Handover OTP is generated only when finder confirms owner
        if self.finder_verified and not self.handover_otp:
            self.handover_otp = f"{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)

    @property
    def item(self):
        """Returns the item being claimed."""
        if self.match:
            return self.match.found_item or self.match.lost_item
        return None

    @property
    def claimed_answers(self):
        """Convenience alias for answer_text."""
        return self.answer_text

    def __str__(self):
        return f"Claim #{self.id} by {self.claimant.username} [{self.get_status_display()}]"


# Backward-compatibility alias
ItemClaim = OwnershipClaim


class ReturnConfirmation(models.Model):
    """Tracks the final return confirmation from both parties."""
    claim              = models.OneToOneField(OwnershipClaim, on_delete=models.CASCADE,
                                               related_name="return_confirmation")
    finder_confirmed   = models.BooleanField(default=False)
    owner_confirmed    = models.BooleanField(default=False)
    finder_confirmed_at= models.DateTimeField(null=True, blank=True)
    owner_confirmed_at = models.DateTimeField(null=True, blank=True)

    def is_complete(self):
        return self.finder_confirmed and self.owner_confirmed

    def __str__(self):
        return f"Return #{self.id} — finder={self.finder_confirmed} owner={self.owner_confirmed}"
