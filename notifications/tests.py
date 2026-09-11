from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from notifications.models import Notification

User = get_user_model()


class NotificationAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123",
            is_email_verified=True,
        )

    def test_unread_latest_includes_chat_and_official_messages(self):
        self.client.login(username="testuser", password="password123")

        # Create official notifications
        n1 = Notification.objects.create(
            user=self.user,
            notif_type=Notification.TYPE_MATCH,
            title="Potential Match Found",
            body="An item matching your iPhone was found.",
            link="/matching/1/",
        )
        n2 = Notification.objects.create(
            user=self.user,
            notif_type=Notification.TYPE_CLAIM,
            title="Claim Status Updated",
            body="Your claim is being reviewed.",
            link="/claims/1/",
        )
        # Create a chat notification (now included in browser push so user gets alerted on PC/mobile)
        n3 = Notification.objects.create(
            user=self.user,
            notif_type=Notification.TYPE_CHAT,
            title="New Chat Message",
            body="Hey, where can we meet?",
            link="/chat/1/",
        )

        res = self.client.get("/notifications/unread-latest/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["unread_count"], 3)
        self.assertEqual(len(data["notifications"]), 3)

        titles = [item["title"] for item in data["notifications"]]
        self.assertIn("Potential Match Found", titles)
        self.assertIn("Claim Status Updated", titles)
        self.assertIn("New Chat Message", titles)

    def test_unread_latest_since_id(self):
        self.client.login(username="testuser", password="password123")
        n1 = Notification.objects.create(
            user=self.user,
            notif_type=Notification.TYPE_MATCH,
            title="Match 1",
            body="Match 1 body",
        )
        n2 = Notification.objects.create(
            user=self.user,
            notif_type=Notification.TYPE_MATCH,
            title="Match 2",
            body="Match 2 body",
        )

        res = self.client.get(f"/notifications/unread-latest/?since_id={n1.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["official_notifications"]), 1)
        self.assertEqual(data["official_notifications"][0]["id"], n2.id)

