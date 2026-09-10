import random
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    email        = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    avatar       = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio          = models.TextField(max_length=300, blank=True)

    # Verification & trust
    is_email_verified = models.BooleanField(default=False)
    trust_score       = models.IntegerField(default=100, help_text="Reputation score 0–200")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({'✓' if self.is_email_verified else '✗'})"

    def get_full_name_or_username(self):
        name = super().get_full_name()
        return name.strip() if name.strip() else self.username


class EmailOTP(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    otp_code   = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    @classmethod
    def generate_otp(cls, user):
        code = f"{random.randint(100000, 999999)}"
        return cls.objects.create(user=user, otp_code=code)

    def is_valid(self):
        now = timezone.now()
        return (now <= self.created_at + timedelta(minutes=10)) and not self.is_used

    def __str__(self):
        return f"OTP {self.otp_code} for {self.user.email}"
