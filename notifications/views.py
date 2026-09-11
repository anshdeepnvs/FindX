from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification


@login_required
def notification_list(request):
    notifs = request.user.notifications.all()[:50]
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/list.html', {'notifications': notifs})


@login_required
@require_POST
def mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('notifications:list')


@login_required
def unread_latest(request):
    """
    Returns unread official notifications for the current user.
    Excludes individual CHAT messages so email and browser notifications
    are reserved strictly for official platform events (MATCH, CLAIM, RETURN, SYSTEM).
    """
    since_id = request.GET.get('since_id')
    qs = request.user.notifications.filter(is_read=False).exclude(notif_type=Notification.TYPE_CHAT)
    if since_id and since_id.isdigit():
        qs = qs.filter(id__gt=int(since_id))

    latest = [
        {
            'id': n.id,
            'type': n.notif_type,
            'title': n.title,
            'body': n.body,
            'link': n.link or '/notifications/',
            'icon': n.icon,
            'created_at': n.created_at.strftime('%I:%M %p'),
        }
        for n in qs.order_by('id')[:10]
    ]

    total_unread = request.user.notifications.filter(is_read=False).count()

    return JsonResponse({
        'unread_count': total_unread,
        'official_notifications': latest,
    })
