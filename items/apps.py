from django.apps import AppConfig
from django.db.models.signals import post_migrate


def seed_categories_callback(sender, **kwargs):
    from .categories_data import auto_seed_categories
    auto_seed_categories()


class ItemsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'items'

    def ready(self):
        post_migrate.connect(seed_categories_callback, sender=self)
