import io
from PIL import Image
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from items.models import Item, Category, PrivateDetail
from matching.models import Match
from matching.scoring import compute_match_score, score_image, score_text
from matching.image_matching import calculate_image_similarity
from matching.services import run_matching

User = get_user_model()


def _create_test_image(color=(0, 0, 255), size=(100, 100)):
    """Generates an in-memory test image as a SimpleUploadedFile."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile("test.jpg", buf.read(), content_type="image/jpeg")


class ImageMatchingTests(TestCase):
    def test_identical_image_similarity(self):
        img_a = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img_b = Image.new("RGB", (100, 100), color=(255, 0, 0))
        sim = calculate_image_similarity(img_a, img_b)
        self.assertGreaterEqual(sim, 0.95)

    def test_different_image_similarity(self):
        img_a = Image.new("RGB", (100, 100), color=(255, 0, 0))  # Red
        img_b = Image.new("RGB", (100, 100), color=(0, 255, 0))  # Green
        sim = calculate_image_similarity(img_a, img_b)
        self.assertLess(sim, 0.60)

    def test_none_image_handling(self):
        sim = calculate_image_similarity(None, None)
        self.assertEqual(sim, 0.0)


class MatchingEngineTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(
            username="alice", email="alice@example.com", password="password123", is_email_verified=True
        )
        self.user_b = User.objects.create_user(
            username="bob", email="bob@example.com", password="password123", is_email_verified=True
        )
        self.cat = Category.objects.create(name="Electronics", slug="electronics", icon="📱")

    def test_adaptive_weights_when_no_images(self):
        # Two items matching in text, category, color, location, and date without images
        lost = Item.objects.create(
            reporter=self.user_a,
            item_type=Item.TYPE_LOST,
            title="Lost iPhone 14 Pro Max in Blue",
            category=self.cat,
            color="blue",
            city="Delhi",
            date_event=timezone.now().date(),
            description="Lost my blue iPhone 14 Pro Max near metro platform.",
            status=Item.STATUS_ACTIVE,
        )
        found = Item.objects.create(
            reporter=self.user_b,
            item_type=Item.TYPE_FOUND,
            title="Found Blue iPhone 14 Pro Max",
            category=self.cat,
            color="blue",
            city="Delhi",
            date_event=timezone.now().date(),
            description="Found a blue Apple iPhone 14 Pro Max smartphone on metro station.",
            status=Item.STATUS_ACTIVE,
        )

        scores = compute_match_score(lost, found)
        # Without images, adaptive weights should still yield a strong score >= 75%
        self.assertGreaterEqual(scores["final_score"], 75.0)

    def test_synchronous_matching_and_status_endpoint(self):
        self.client.login(username="alice", password="password123")
        
        # Bob reports a found item first
        found = Item.objects.create(
            reporter=self.user_b,
            item_type=Item.TYPE_FOUND,
            title="Found Titan Silver Watch",
            category=self.cat,
            color="silver",
            city="Mumbai",
            date_event=timezone.now().date(),
            description="Found a silver Titan analog watch in coffee shop.",
            status=Item.STATUS_ACTIVE,
        )

        # Alice reports lost item
        lost = Item.objects.create(
            reporter=self.user_a,
            item_type=Item.TYPE_LOST,
            title="Lost Titan Watch in Silver",
            category=self.cat,
            color="silver",
            city="Mumbai",
            date_event=timezone.now().date(),
            description="Lost silver Titan watch at cafe in Mumbai.",
            status=Item.STATUS_ACTIVE,
        )

        # Run matching
        count = run_matching(lost)
        self.assertGreaterEqual(count, 1)

        # Check detail page shows matches
        res = self.client.get(f"/items/{lost.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Found Titan Silver Watch")

        # Test AJAX status endpoint
        res_ajax = self.client.get(f"/items/{lost.id}/matches-status/")
        self.assertEqual(res_ajax.status_code, 200)
        data = res_ajax.json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertEqual(data["matches"][0]["title"], "Found Titan Silver Watch")
