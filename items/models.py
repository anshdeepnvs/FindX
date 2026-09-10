from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True, blank=True)
    icon        = models.CharField(max_length=10, default="📦")
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.icon} {self.name}"


class Item(models.Model):
    TYPE_LOST  = "LOST"
    TYPE_FOUND = "FOUND"
    ITEM_TYPE_CHOICES = (
        (TYPE_LOST,  "Lost — I lost this item"),
        (TYPE_FOUND, "Found — I found this item"),
    )

    STATUS_ACTIVE       = "ACTIVE"
    STATUS_MATCH_FOUND  = "MATCH_FOUND"
    STATUS_CLAIM_PENDING= "CLAIM_PENDING"
    STATUS_VERIFIED     = "VERIFIED"
    STATUS_RETURNED     = "RETURNED"
    STATUS_CLOSED       = "CLOSED"
    STATUS_CHOICES = (
        (STATUS_ACTIVE,        "Active"),
        (STATUS_MATCH_FOUND,   "Match Found"),
        (STATUS_CLAIM_PENDING, "Claim Pending"),
        (STATUS_VERIFIED,      "Ownership Verified"),
        (STATUS_RETURNED,      "Returned"),
        (STATUS_CLOSED,        "Closed"),
    )

    reporter   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="reported_items")
    item_type  = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)

    # Basic info
    title       = models.CharField(max_length=150)
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True,
                                    related_name="items")
    brand       = models.CharField(max_length=100, blank=True)
    color       = models.CharField(max_length=80, blank=True, help_text="e.g. Black, Silver, Navy Blue")
    description = models.TextField(help_text="Public description — do NOT include secret identifying details.")

    # Location
    location_name   = models.CharField(max_length=200, blank=True, help_text="Landmark, station, etc.")
    city            = models.CharField(max_length=100)
    state           = models.CharField(max_length=100, blank=True)
    country         = models.CharField(max_length=100, default="India")
    latitude        = models.FloatField(null=True, blank=True)
    longitude       = models.FloatField(null=True, blank=True)

    # Time
    date_event = models.DateField(help_text="Date when item was lost or found")
    time_event = models.TimeField(null=True, blank=True, help_text="Approximate time (optional)")

    # Primary image
    image = models.ImageField(upload_to="item_photos/", blank=True, null=True)

    # AI embedding stored as JSON text (comma-separated floats)
    embedding_json = models.TextField(blank=True, help_text="Internal: serialized text embedding vector")

    # Status
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.item_type}] {self.title} — {self.city}"

    @property
    def type_label(self):
        return "Lost" if self.item_type == self.TYPE_LOST else "Found"

    @property
    def status_badge_class(self):
        mapping = {
            self.STATUS_ACTIVE:        "badge-active",
            self.STATUS_MATCH_FOUND:   "badge-match",
            self.STATUS_CLAIM_PENDING: "badge-pending",
            self.STATUS_VERIFIED:      "badge-verified",
            self.STATUS_RETURNED:      "badge-returned",
            self.STATUS_CLOSED:        "badge-closed",
        }
        return mapping.get(self.status, "badge-active")

    @property
    def hidden_details(self):
        try:
            return self.private_detail.hidden_info if hasattr(self, 'private_detail') and self.private_detail else ""
        except Exception:
            return ""

    @property
    def challenge_question(self):
        try:
            return self.private_detail.challenge_question if hasattr(self, 'private_detail') and self.private_detail else ""
        except Exception:
            return ""

    @property
    def serial_hint(self):
        try:
            return self.private_detail.serial_hint if hasattr(self, 'private_detail') and self.private_detail else ""
        except Exception:
            return ""

    def get_embedding(self):
        """Return embedding as list of floats, or empty list."""
        if not self.embedding_json:
            return []
        try:
            return [float(x) for x in self.embedding_json.split(",")]
        except Exception:
            return []

    def set_embedding(self, vector):
        """Store numpy/list vector as comma-separated string."""
        self.embedding_json = ",".join(f"{v:.6f}" for v in vector)


class ItemImage(models.Model):
    """Additional images for an item (beyond the primary image field)."""
    item       = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="extra_images")
    image      = models.ImageField(upload_to="item_photos/extra/")
    caption    = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.item.title}"


class PrivateDetail(models.Model):
    """
    Anti-scam private verification details — NEVER shown publicly.
    Only used to verify the true owner during a claim.
    """
    item              = models.OneToOneField(Item, on_delete=models.CASCADE,
                                             related_name="private_detail")
    hidden_info       = models.TextField(help_text="Unique marks, contents, scratches, stickers, etc.")
    challenge_question= models.CharField(max_length=255, blank=True,
                                          default="Describe the unique private marks or contents of the item.")
    serial_hint       = models.CharField(max_length=100, blank=True,
                                          help_text="Last 4 digits of serial / IMEI — optional")
    additional_notes  = models.TextField(blank=True)

    def __str__(self):
        return f"Private details for: {self.item.title}"
