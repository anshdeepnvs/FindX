from django.apps import AppConfig


class MatchingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "matching"
    verbose_name = "AI Matching"

    def ready(self):
        import matching.signals  # noqa: F401 — registers signals
