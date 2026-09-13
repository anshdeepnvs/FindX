import os
import io
from PIL import Image

from django.test import TestCase, Client
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.conf import settings

from core.models import DatabaseFile


class DatabaseMediaStorageTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Generate a small valid 100x100 test JPEG image in memory
        img = Image.new("RGB", (100, 100), color="blue")
        out = io.BytesIO()
        img.save(out, format="JPEG")
        self.test_img_bytes = out.getvalue()
        self.test_file_name = "test_items/test_blue_box.jpg"

    def tearDown(self):
        # Cleanup disk and DB
        default_storage.delete(self.test_file_name)
        disk_path = os.path.join(settings.MEDIA_ROOT, self.test_file_name.replace("/", os.sep))
        if os.path.exists(disk_path):
            try:
                os.remove(disk_path)
            except Exception:
                pass

    def test_database_storage_save_and_query(self):
        saved_name = default_storage.save(self.test_file_name, ContentFile(self.test_img_bytes))
        self.assertEqual(saved_name, self.test_file_name)

        # 1. Verify saved in PostgreSQL DatabaseFile table
        db_file = DatabaseFile.objects.filter(name=self.test_file_name).first()
        self.assertIsNotNone(db_file)
        self.assertEqual(db_file.content_type, "image/jpeg")
        self.assertGreater(db_file.size, 0)
        self.assertEqual(len(db_file.content), db_file.size)

        # 2. Verify exists() and url()
        self.assertTrue(default_storage.exists(self.test_file_name))
        self.assertEqual(default_storage.url(self.test_file_name), f"/media/{self.test_file_name}")

    def test_server_restart_restores_from_database(self):
        # Save file to DB and disk
        default_storage.save(self.test_file_name, ContentFile(self.test_img_bytes))

        # SIMULATE RENDER RESTART: Delete local disk file
        disk_path = os.path.join(settings.MEDIA_ROOT, self.test_file_name.replace("/", os.sep))
        if os.path.exists(disk_path):
            os.remove(disk_path)
        self.assertFalse(os.path.exists(disk_path), "Local disk file should be gone (simulating restart).")

        # Request via HTTP /media/ endpoint
        response = self.client.get(f"/media/{self.test_file_name}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/jpeg")
        self.assertIn("max-age=31536000", response.headers.get("Cache-Control", ""))

        # Verify disk cache has been restored!
        self.assertTrue(os.path.exists(disk_path), "Local disk file should be dynamically restored!")

    def test_serve_media_404_when_missing(self):
        response = self.client.get("/media/non_existent_file_xyz.jpg")
        self.assertEqual(response.status_code, 404)

    def test_sync_media_command(self):
        out = io.StringIO()
        call_command("sync_media_to_db", stdout=out)
        self.assertIn("Media sync complete", out.getvalue())

