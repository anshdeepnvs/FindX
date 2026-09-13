from django.db import models


class DatabaseFile(models.Model):
    """
    Stores uploaded media files (item photos, avatars, proofs) directly inside PostgreSQL.
    Guarantees 100% permanence on platforms with ephemeral disks (like Render).
    """
    name = models.CharField(max_length=255, unique=True, db_index=True)
    content = models.BinaryField()
    content_type = models.CharField(max_length=100, default="image/jpeg")
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Database File"
        verbose_name_plural = "Database Files"

    def __str__(self):
        return f"{self.name} ({self.size} bytes)"
