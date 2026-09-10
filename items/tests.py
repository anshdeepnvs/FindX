from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Item, Category, PrivateDetail

User = get_user_model()


class ItemsAntiScamTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.reporter = User.objects.create_user(
            username="finder1",
            email="finder1@example.com",
            password="password123",
            is_email_verified=True
        )
        self.stranger = User.objects.create_user(
            username="stranger",
            email="stranger@example.com",
            password="password123",
            is_email_verified=True
        )
        self.category = Category.objects.create(name="Wallets", icon="👛")
        self.item = Item.objects.create(
            reporter=self.reporter,
            item_type="FOUND",
            title="Black Tommy Hilfiger Wallet",
            category=self.category,
            city="Delhi",
            location_name="Airport Gate 1",
            date_event=timezone.now().date(),
            description="Public info: Black wallet found.",
            status="ACTIVE"
        )
        self.private = PrivateDetail.objects.create(
            item=self.item,
            hidden_info="SECRET_SBI_CARD_NUMBER_7788_AND_STUDENT_ID",
            challenge_question="What card is inside?",
        )

    def test_anonymous_user_cannot_see_hidden_details(self):
        response = self.client.get(f"/items/{self.item.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET_SBI_CARD_NUMBER_7788_AND_STUDENT_ID")
        self.assertContains(response, "Black wallet found.")

    def test_other_user_cannot_see_hidden_details(self):
        self.client.login(username="stranger", password="password123")
        response = self.client.get(f"/items/{self.item.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET_SBI_CARD_NUMBER_7788_AND_STUDENT_ID")

    def test_reporter_can_see_hidden_details(self):
        self.client.login(username="finder1", password="password123")
        response = self.client.get(f"/items/{self.item.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SECRET_SBI_CARD_NUMBER_7788_AND_STUDENT_ID")
