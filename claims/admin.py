from django.contrib import admin
from .models import OwnershipClaim, ReturnConfirmation


@admin.register(OwnershipClaim)
class OwnershipClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "claimant", "match", "status", "created_at")
    list_filter  = ("status", "created_at")
    search_fields= ("claimant__username", "answer_text")


@admin.register(ReturnConfirmation)
class ReturnConfirmationAdmin(admin.ModelAdmin):
    list_display = ("id", "claim", "finder_confirmed", "owner_confirmed")
