"""
sync_media_to_db.py — Management command to synchronize media files into PostgreSQL.

Scans settings.MEDIA_ROOT and ensures every uploaded image is safely preserved
in the DatabaseFile model in Neon PostgreSQL.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import DatabaseFile
from core.storage import _optimize_image_bytes


class Command(BaseCommand):
    help = "Sync all local media files into the PostgreSQL DatabaseFile table for permanent storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing database records with current disk files.",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)
        media_root = str(settings.MEDIA_ROOT)

        if not os.path.exists(media_root):
            self.stdout.write(self.style.WARNING(f"Media root does not exist: {media_root}"))
            return

        synced_count = 0
        skipped_count = 0
        error_count = 0
        total_bytes = 0

        self.stdout.write(self.style.MIGRATE_HEADING("Scanning media directory for files to sync..."))

        for root, _, files in os.walk(media_root):
            for filename in files:
                if filename.startswith(".") or filename == ".gitkeep":
                    continue

                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, media_root).replace("\\", "/")

                if not force and DatabaseFile.objects.filter(name=rel_path).exists():
                    skipped_count += 1
                    continue

                try:
                    with open(abs_path, "rb") as f:
                        raw_bytes = f.read()

                    optimized_bytes, content_type = _optimize_image_bytes(raw_bytes)

                    DatabaseFile.objects.update_or_create(
                        name=rel_path,
                        defaults={
                            "content": optimized_bytes,
                            "content_type": content_type,
                            "size": len(optimized_bytes),
                        },
                    )
                    synced_count += 1
                    total_bytes += len(optimized_bytes)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [SYNCED] {rel_path} ({len(optimized_bytes)} bytes, {content_type})"
                        )
                    )
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"  [ERROR] {rel_path}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nMedia sync complete: {synced_count} synced ({total_bytes / 1024:.1f} KB), "
                f"{skipped_count} already up-to-date, {error_count} errors."
            )
        )
