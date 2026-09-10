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
    return render(request, 'home/index.html', {'stats': stats})


@login_required
def dashboard(request):
    user = request.user
    my_items = user.reported_items.filter(is_active=True).select_related('category').order_by('-created_at')

    lost_items  = my_items.filter(item_type='LOST')
    found_items = my_items.filter(item_type='FOUND')

    # Matches involving this user
    my_lost_ids  = lost_items.values_list('id', flat=True)
    my_found_ids = found_items.values_list('id', flat=True)
    matches = Match.objects.filter(
        lost_item_id__in=my_lost_ids
    ) | Match.objects.filter(
        found_item_id__in=my_found_ids
    )
    matches = matches.exclude(status=Match.STATUS_RETURNED).order_by('-final_score')[:5]

    # Pending claims on my found items
    pending_claims = OwnershipClaim.objects.filter(
        match__found_item__reporter=user,
        status=OwnershipClaim.STATUS_PENDING,
    ).select_related('claimant', 'match__lost_item').order_by('-created_at')[:5]

    # My submitted claims
    my_claims = user.ownership_claims.exclude(
        status=OwnershipClaim.STATUS_CANCELLED
    ).select_related('match__found_item').order_by('-created_at')[:5]

    # Recent notifications
    notifications = user.notifications.filter(is_read=False)[:5]

    # Unread chat count
    from chat.models import Conversation
    my_convos = Conversation.objects.filter(
        participant_a=user
    ) | Conversation.objects.filter(participant_b=user)
    unread_msgs = sum(c.unread_count(user) for c in my_convos[:20])

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
