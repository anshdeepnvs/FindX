from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def staff_required(view_func):
    """Restricts access to staff/admin users only."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access the admin panel.")
            return redirect("accounts:login")
        if not request.user.is_staff:
            messages.error(request, "⛔ Access denied. Admin panel is restricted to staff members only.")
            return redirect("core:home")
        return view_func(request, *args, **kwargs)
    return _wrapped
