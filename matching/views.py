from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Match


@login_required
def match_list(request):
    user = request.user
    # Get matches involving this user's items
    from items.models import Item
    my_lost_ids  = user.reported_items.filter(item_type=Item.TYPE_LOST, is_active=True).values_list('id', flat=True)
    my_found_ids = user.reported_items.filter(item_type=Item.TYPE_FOUND, is_active=True).values_list('id', flat=True)

    from django.db.models import Q
    matches = Match.objects.filter(
        Q(lost_item_id__in=my_lost_ids) | Q(found_item_id__in=my_found_ids)
    ).exclude(
        status__in=[Match.STATUS_REJECTED, Match.STATUS_RETURNED]
    ).exclude(
        lost_item__status__in=['RETURNED', 'CLOSED']
    ).exclude(
        found_item__status__in=['RETURNED', 'CLOSED']
    ).select_related(
        'lost_item', 'found_item', 'lost_item__reporter', 'found_item__reporter'
    ).order_by('-final_score')

    ctx = {'matches': matches}
    return render(request, 'matching/match_list.html', ctx)


@login_required
def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.select_related(
            'lost_item', 'found_item',
            'lost_item__reporter', 'found_item__reporter',
            'lost_item__category', 'found_item__category',
        ),
        pk=pk
    )

    # Security: only involved parties can view
    user = request.user
    if user != match.lost_item.reporter and user != match.found_item.reporter:
        messages.error(request, 'You do not have access to this match.')
        return redirect('core:dashboard')

    # Check if conversation exists
    conversation = None
    try:
        conversation = match.conversation
    except Exception:
        pass

    # Check if claim exists
    claim = match.claims.filter(claimant=user).first() if match.claims.exists() else None

    is_lost_reporter  = user == match.lost_item.reporter
    is_found_reporter = user == match.found_item.reporter

    ctx = {
        'match': match,
        'conversation': conversation,
        'claim': claim,
        'is_lost_reporter': is_lost_reporter,
        'is_found_reporter': is_found_reporter,
    }
    return render(request, 'matching/match_detail.html', ctx)
