from django.db import models
from django.conf import settings
from matching.models import Match


class Conversation(models.Model):
    """A secure chat channel between matched users."""
    STATUS_AI_VERIFY     = "AI_VERIFICATION"
    STATUS_PENDING_FINDER= "PENDING_FINDER"
    STATUS_ACTIVE        = "ACTIVE"
    STATUS_CLOSED        = "CLOSED"
    STATUS_CHOICES = (
        (STATUS_AI_VERIFY,      "AI Verification"),
        (STATUS_PENDING_FINDER, "AI Verified — Awaiting Finder"),
        (STATUS_ACTIVE,         "Active Handover Chat"),
        (STATUS_CLOSED,         "Closed — Item Returned"),
    )

    match         = models.OneToOneField(Match, on_delete=models.CASCADE,
                                          related_name="conversation")
    participant_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name="conversations_as_a")
    participant_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name="conversations_as_b")
    status        = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    ai_score      = models.FloatField(null=True, blank=True)
    is_ai_verified= models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    is_active     = models.BooleanField(default=True)

    def __str__(self):
        return f"Chat: {self.participant_a.username} ↔ {self.participant_b.username} [{self.status}]"

    def other_participant(self, user):
        return self.participant_b if self.participant_a == user else self.participant_a

    def unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    @property
    def is_closed(self):
        return (not self.is_active) or (self.status == self.STATUS_CLOSED) or (self.match.status == Match.STATUS_RETURNED)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                      related_name="messages")
    sender       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="sent_messages", null=True, blank=True)
    is_ai        = models.BooleanField(default=False)
    content      = models.TextField(blank=True, default="")
    image        = models.ImageField(upload_to="chat_proofs/", blank=True, null=True)
    message_type = models.CharField(max_length=20, default="TEXT")
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        name = "AI Officer" if self.is_ai else (self.sender.username if self.sender else "System")
        return f"Msg from {name}: {self.content[:40]}"
