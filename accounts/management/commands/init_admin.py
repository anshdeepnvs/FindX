import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Initializes default admin superuser for deployment without requiring interactive shell."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("ADMIN_USERNAME", "admin").strip()
        email = os.getenv("ADMIN_EMAIL", "admin@findx.local").strip()
        password = os.getenv("ADMIN_PASSWORD", "admin123").strip()

        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"[OK] Initialized superuser '{username}' successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] Updated superuser '{username}' successfully."))
