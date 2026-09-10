def notify_user(user, notif_type, title, body="", link=""):
    """Create an in-app Notification record. Safe to call from anywhere."""
    try:
        from notifications.models import Notification
        Notification.objects.create(
            user=user,
            notif_type=notif_type,
            title=title,
            body=body,
            link=link,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"notify_user failed: {e}")
