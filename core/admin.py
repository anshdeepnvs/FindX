from django.contrib import admin
from core.models import DatabaseFile


@admin.register(DatabaseFile)
class DatabaseFileAdmin(admin.ModelAdmin):
    list_display = ("name", "content_type", "size_formatted", "created_at", "updated_at")
    search_fields = ("name", "content_type")
    readonly_fields = ("name", "content_type", "size", "created_at", "updated_at")
    ordering = ("-created_at",)

    def size_formatted(self, obj):
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        return f"{obj.size / (1024 * 1024):.2f} MB"

    size_formatted.short_description = "Size"

