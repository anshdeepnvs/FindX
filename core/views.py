from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from items.models import Item
from matching.models import Match
from claims.models import OwnershipClaim

User = get_user_model()


def home(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    # Live stats
    stats = {
        'total_items':     Item.objects.count(),
        'active_items':    Item.objects.filter(is_active=True).count(),
        'total_matches':   Match.objects.count(),
        'returned_items':  Item.objects.filter(status='RETURNED').count(),
        'total_users':     User.objects.filter(is_email_verified=True).count(),
    }
    recent_found = Item.objects.filter(item_type='FOUND', is_active=True).select_related('category').order_by('-created_at')[:4]
    recent_lost = Item.objects.filter(item_type='LOST', is_active=True).select_related('category').order_by('-created_at')[:4]
    recent_items = Item.objects.filter(is_active=True).select_related('category').order_by('-created_at')[:6]

    context = {
        'stats': stats,
        'recent_found': recent_found,
        'recent_lost': recent_lost,
        'recent_items': recent_items,
    }
    return render(request, 'home/index.html', context)


@login_required
def dashboard(request):
    user = request.user
    my_items = user.reported_items.filter(is_active=True).select_related('category').order_by('-created_at')

    lost_items  = my_items.filter(item_type='LOST')
    found_items = my_items.filter(item_type='FOUND')

    # Matches involving this user (with optimized select_related to prevent N+1 queries)
    my_lost_ids  = lost_items.values_list('id', flat=True)
    my_found_ids = found_items.values_list('id', flat=True)
    matches = (
        Match.objects.filter(lost_item_id__in=my_lost_ids)
        | Match.objects.filter(found_item_id__in=my_found_ids)
    ).exclude(
        status=Match.STATUS_RETURNED
    ).select_related(
        'lost_item', 'found_item', 'lost_item__category', 'found_item__category', 'found_item__reporter', 'lost_item__reporter'
    ).order_by('-final_score')[:5]

    # Pending claims on my found items
    pending_claims = OwnershipClaim.objects.filter(
        match__found_item__reporter=user,
        status=OwnershipClaim.STATUS_PENDING,
    ).select_related('claimant', 'match__lost_item', 'match__found_item').order_by('-created_at')[:5]

    # My submitted claims
    my_claims = user.ownership_claims.exclude(
        status=OwnershipClaim.STATUS_CANCELLED
    ).select_related('match__found_item', 'match__lost_item', 'match__found_item__category').order_by('-created_at')[:5]

    # Recent notifications
    notifications = user.notifications.filter(is_read=False)[:5]

    # Unread chat count — executed in 1 single fast query
    from chat.models import Conversation, Message
    my_convos = Conversation.objects.filter(
        participant_a=user
    ) | Conversation.objects.filter(participant_b=user)
    unread_msgs = Message.objects.filter(
        conversation__in=my_convos, is_read=False
    ).exclude(sender=user).count()

    ctx = {
        'lost_count':   lost_items.count(),
        'found_count':  found_items.count(),
        'match_count':  matches.count(),
        'pending_claim_count': pending_claims.count(),
        'returned_count': user.reported_items.filter(status='RETURNED').count(),
        'recent_items':  my_items[:6],
        'matches':       matches,
        'pending_claims':pending_claims,
        'my_claims':     my_claims,
        'notifications': notifications,
        'unread_msgs':   unread_msgs,
    }
    return render(request, 'dashboard/dashboard.html', ctx)


import os
import mimetypes
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings


def serve_media(request, path):
    """
    Production-ready media server that streams files with aggressive HTTP caching.
    If the file is not on the ephemeral local disk (e.g. after Render restart),
    it dynamically restores and streams it from PostgreSQL (Neon).
    """
    from core.models import DatabaseFile

    clean_path = path.replace("\\", "/").lstrip("/")
    local_path = os.path.join(settings.MEDIA_ROOT, clean_path.replace("/", os.sep))

    # 1. If file exists on local disk, serve immediately
    if os.path.exists(local_path) and os.path.isfile(local_path):
        content_type, _ = mimetypes.guess_type(local_path)
        resp = FileResponse(open(local_path, "rb"), content_type=content_type or "application/octet-stream")
        resp["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    # 2. Server restarted — Fetch from PostgreSQL (Neon) DatabaseFile
    db_file = DatabaseFile.objects.filter(name=clean_path).first()
    if db_file:
        # Restore local disk cache so subsequent hits don't touch the DB
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(db_file.content)
        except Exception:
            pass

        resp = HttpResponse(db_file.content, content_type=db_file.content_type)
        resp["Content-Length"] = db_file.size
        resp["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    raise Http404("Media file not found.")

