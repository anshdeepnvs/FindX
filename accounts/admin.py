from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, EmailOTP


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_email_verified", "trust_score", "is_staff")
    list_filter = ("is_email_verified", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (
        ("Verification & Anti-Scam", {"fields": ("is_email_verified", "phone_number", "trust_score")}),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "otp_code", "created_at", "is_used")
    list_filter = ("is_used", "created_at")
