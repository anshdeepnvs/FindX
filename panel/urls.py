from django.urls import path
from . import views

app_name = "panel"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/verify/", views.user_verify, name="user_verify"),
    path("users/<int:user_id>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    path("users/<int:user_id>/toggle-staff/", views.user_toggle_staff, name="user_toggle_staff"),
    path("users/<int:user_id>/trust/", views.user_adjust_trust, name="user_adjust_trust"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),

    # Items
    path("items/", views.item_list, name="item_list"),
    path("items/<int:item_id>/", views.item_detail, name="item_detail"),
    path("items/<int:item_id>/status/", views.item_change_status, name="item_change_status"),
    path("items/<int:item_id>/delete/", views.item_delete, name="item_delete"),

    # Claims
    path("claims/", views.claim_list, name="claim_list"),
    path("claims/<int:claim_id>/", views.claim_detail, name="claim_detail"),
    path("claims/<int:claim_id>/status/", views.claim_change_status, name="claim_change_status"),
    path("claims/<int:claim_id>/delete/", views.claim_delete, name="claim_delete"),

    # Categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_add, name="category_add"),
    path("categories/<int:cat_id>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:cat_id>/delete/", views.category_delete, name="category_delete"),
]
