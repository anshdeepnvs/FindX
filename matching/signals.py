from django.db.models.signals import post_save
from django.dispatch import receiver
import threading
import sys


@receiver(post_save, sender="items.Item")
def item_post_save(sender, instance, created, **kwargs):
    """
    Trigger matching whenever an item is saved.
    In tests, skip to avoid SQLite multithread/lock issues and keep test runs fast.
    In production/dev, run in a background thread for snappy UI.
    """
    if not instance.is_active or instance.status not in ("ACTIVE", "MATCH_FOUND"):
        return

    # In test runner, skip automatic matching signal (tests call run_matching explicitly if needed)
    if "test" in sys.argv:
        return

    # Prevent recursive trigger when saving embedding or non-matching fields
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        matching_fields = {"title", "description", "brand", "color", "category", "city", "state", "date_event"}
        if not set(update_fields).intersection(matching_fields):
            return

    def _run():
        try:
            from matching.services import run_matching
            run_matching(instance)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Matching signal failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
