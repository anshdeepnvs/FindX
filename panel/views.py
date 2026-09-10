from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.views.decorators.http import require_POST

from .decorators import staff_required
from accounts.models import EmailOTP
from items.models import Item, Category
from matching.models import Match
from claims.models import OwnershipClaim
from notifications.models import Notification

User = get_user_model()


@staff_required
def dashboard(request):
    ctx = {
        "total_users":     User.objects.count(),
        "verified_users":  User.objects.filter(is_email_verified=True).count(),
        "unverified_users":User.objects.filter(is_email_verified=False).count(),
        "total_items":     Item.objects.count(),
        "open_items":      Item.objects.filter(status="ACTIVE").count(),
        "resolved_items":  Item.objects.filter(status="RETURNED").count(),
        "lost_items":      Item.objects.filter(item_type="LOST").count(),
        "found_items":     Item.objects.filter(item_type="FOUND").count(),
        "total_matches":   Match.objects.count(),
        "total_claims":    OwnershipClaim.objects.count(),
        "pending_claims":  OwnershipClaim.objects.filter(status="PENDING").count(),
        "recent_users":    User.objects.order_by("-date_joined")[:8],
        "recent_items":    Item.objects.select_related("reporter", "category").order_by("-created_at")[:8],
        "recent_claims":   OwnershipClaim.objects.select_related("claimant", "match").order_by("-created_at")[:8],
    }
    return render(request, "panel/dashboard.html", ctx)


@staff_required
def user_list(request):
    q      = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    role   = request.GET.get("role", "")
    users  = User.objects.annotate(
        item_count=Count("reported_items", distinct=True),
        claim_count=Count("ownership_claims", distinct=True),
    ).order_by("-date_joined")
    if q:
        users = users.filter(Q(username__icontains=q)|Q(email__icontains=q))
    if status == "verified":   users = users.filter(is_email_verified=True)
    elif status == "unverified": users = users.filter(is_email_verified=False)
    if role == "staff":   users = users.filter(is_staff=True)
    elif role == "normal": users = users.filter(is_staff=False)
    ctx = {"users": users, "q": q, "status": status, "role": role, "total": users.count()}
    return render(request, "panel/users.html", ctx)


@staff_required
def user_detail(request, user_id):
    target = get_object_or_404(User, id=user_id)
    ctx = {
        "target": target,
        "items":  target.reported_items.select_related("category").order_by("-created_at"),
        "claims": target.ownership_claims.select_related("match").order_by("-created_at"),
        "otps":   EmailOTP.objects.filter(user=target).order_by("-created_at")[:10],
    }
    return render(request, "panel/user_detail.html", ctx)


@staff_required
@require_POST
def user_verify(request, user_id):
    target = get_object_or_404(User, id=user_id)
    target.is_email_verified = True; target.save()
    messages.success(request, f"✅ {target.username}'s email verified.")
    return redirect("panel:user_detail", user_id=user_id)


@staff_required
@require_POST
def user_toggle_active(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "Cannot deactivate own account.")
        return redirect("panel:user_detail", user_id=user_id)
    target.is_active = not target.is_active; target.save()
    messages.success(request, f"User {target.username} {'activated' if target.is_active else 'banned'}.")
    return redirect("panel:user_detail", user_id=user_id)


@staff_required
@require_POST
def user_toggle_staff(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "Cannot modify own staff status.")
        return redirect("panel:user_detail", user_id=user_id)
    target.is_staff = not target.is_staff; target.save()
    messages.success(request, f"User {target.username}: staff={target.is_staff}.")
    return redirect("panel:user_detail", user_id=user_id)


@staff_required
@require_POST
def user_adjust_trust(request, user_id):
    target = get_object_or_404(User, id=user_id)
    try:
        score = max(0, min(200, int(request.POST.get("trust_score", target.trust_score))))
        target.trust_score = score; target.save()
        messages.success(request, f"Trust score updated to {score}.")
    except (ValueError, TypeError):
        messages.error(request, "Invalid score value.")
    return redirect("panel:user_detail", user_id=user_id)


@staff_required
@require_POST
def user_delete(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "Cannot delete own account.")
        return redirect("panel:user_detail", user_id=user_id)
    username = target.username; target.delete()
    messages.success(request, f"User '{username}' deleted.")
    return redirect("panel:user_list")


@staff_required
def item_list(request):
    q = request.GET.get("q", "").strip()
    item_type = request.GET.get("type", "")
    status = request.GET.get("status", "")
    items = Item.objects.select_related("reporter", "category").order_by("-created_at")
    if q: items = items.filter(Q(title__icontains=q)|Q(city__icontains=q)|Q(reporter__username__icontains=q))
    if item_type: items = items.filter(item_type=item_type)
    if status: items = items.filter(status=status)
    ctx = {"items": items, "categories": Category.objects.all(), "q": q,
           "filter_type": item_type, "filter_status": status, "total": items.count()}
    return render(request, "panel/items.html", ctx)


@staff_required
def item_detail(request, item_id):
    item = get_object_or_404(Item.objects.select_related("reporter", "category"), id=item_id)
    ctx = {"item": item}
    return render(request, "panel/item_detail.html", ctx)


@staff_required
@require_POST
def item_change_status(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    new_status = request.POST.get("status", "")
    valid = [c[0] for c in Item.STATUS_CHOICES]
    if new_status in valid:
        item.status = new_status; item.save()
        messages.success(request, f"Status updated to '{item.get_status_display()}'.")
    else:
        messages.error(request, "Invalid status.")
    return redirect("panel:item_detail", item_id=item_id)


@staff_required
@require_POST
def item_delete(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    title = item.title; item.delete()
    messages.success(request, f"Item '{title}' deleted.")
    return redirect("panel:item_list")


@staff_required
def claim_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    claims = OwnershipClaim.objects.select_related("claimant", "match").order_by("-created_at")
    if q: claims = claims.filter(Q(claimant__username__icontains=q))
    if status: claims = claims.filter(status=status)
    ctx = {"claims": claims, "q": q, "filter_status": status, "total": claims.count()}
    return render(request, "panel/claims.html", ctx)


@staff_required
def claim_detail(request, claim_id):
    claim = get_object_or_404(OwnershipClaim.objects.select_related("claimant", "match"), id=claim_id)
    ctx = {"claim": claim}
    return render(request, "panel/claim_detail.html", ctx)


@staff_required
@require_POST
def claim_change_status(request, claim_id):
    claim = get_object_or_404(OwnershipClaim, id=claim_id)
    new_status = request.POST.get("status", "")
    valid = [c[0] for c in OwnershipClaim.STATUS_CHOICES]
    if new_status in valid:
        claim.status = new_status; claim.save()
        messages.success(request, f"Claim status updated.")
    return redirect("panel:claim_detail", claim_id=claim_id)


@staff_required
@require_POST
def claim_delete(request, claim_id):
    claim = get_object_or_404(OwnershipClaim, id=claim_id)
    pk = claim.id; claim.delete()
    messages.success(request, f"Claim #{pk} deleted.")
    return redirect("panel:claim_list")


@staff_required
def category_list(request):
    cats = Category.objects.annotate(item_count=Count("items")).order_by("name")
    return render(request, "panel/categories.html", {"categories": cats})


@staff_required
@require_POST
def category_add(request):
    name = request.POST.get("name", "").strip()
    icon = request.POST.get("icon", "📦").strip()
    desc = request.POST.get("description", "").strip()
    if not name: messages.error(request, "Name is required.")
    elif Category.objects.filter(name__iexact=name).exists(): messages.error(request, f"'{name}' already exists.")
    else:
        Category.objects.create(name=name, icon=icon, description=desc)
        messages.success(request, f"Category '{name}' created.")
    return redirect("panel:category_list")


@staff_required
@require_POST
def category_edit(request, cat_id):
    cat = get_object_or_404(Category, id=cat_id)
    name = request.POST.get("name", "").strip()
    if not name: messages.error(request, "Name required.")
    else:
        cat.name = name; cat.icon = request.POST.get("icon", "📦").strip()
        cat.description = request.POST.get("description", "").strip(); cat.save()
        messages.success(request, f"Category updated.")
    return redirect("panel:category_list")


@staff_required
@require_POST
def category_delete(request, cat_id):
    cat = get_object_or_404(Category, id=cat_id)
    name = cat.name; cat.delete()
    messages.success(request, f"Category '{name}' deleted.")
    return redirect("panel:category_list")
