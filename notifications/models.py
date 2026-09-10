from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_MATCH   = "MATCH"
    TYPE_CLAIM   = "CLAIM"
    TYPE_CHAT    = "CHAT"
    TYPE_RETURN  = "RETURN"
    TYPE_SYSTEM  = "SYSTEM"
    TYPE_CHOICES = (
        (TYPE_MATCH,  "Potential Match Found"),
        (TYPE_CLAIM,  "Claim Update"),
        (TYPE_CHAT,   "New Message"),
        (TYPE_RETURN, "Return Update"),
        (TYPE_SYSTEM, "System Notification"),
    )

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="notifications")
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True)
    link       = models.CharField(max_length=300, blank=True)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.notif_type}] {self.title} → {self.user.username}"

    @property
    def icon(self):
        icons = {
            self.TYPE_MATCH:  "🔍",
            self.TYPE_CLAIM:  "📋",
            self.TYPE_CHAT:   "💬",
            self.TYPE_RETURN: "🎉",
            self.TYPE_SYSTEM: "🔔",
        }
        return icons.get(self.notif_type, "🔔")
