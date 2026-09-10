from django.contrib import admin
from .models import Category, Item, ItemImage, PrivateDetail


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1


class PrivateDetailInline(admin.StackedInline):
    model = PrivateDetail
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display  = ("title", "item_type", "category", "city", "status", "is_active", "reporter", "created_at")
    list_filter   = ("item_type", "status", "is_active", "category", "created_at")
    search_fields = ("title", "description", "city", "brand", "color", "reporter__username")
    inlines       = [PrivateDetailInline, ItemImageInline]
