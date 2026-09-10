from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from items.models import Item, Category, PrivateDetail
from matching.models import Match
from claims.models import OwnershipClaim, ReturnConfirmation
from chat.models import Conversation, Message

User = get_user_model()


class FindXFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.finder = User.objects.create_user(
            username="finder", email="finder@example.com", password="password123", is_email_verified=True
        )
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="password123", is_email_verified=True
        )
        self.cat = Category.objects.create(name="Electronics", icon="📱")
        
        self.lost_item = Item.objects.create(
            reporter=self.owner,
            item_type="LOST",
            title="Lost iPhone 14 with blue case",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Lost my blue iPhone at Rajiv Chowk metro.",
            status="ACTIVE"
        )
        self.private = PrivateDetail.objects.create(
            item=self.lost_item,
            hidden_info="White husky dog wallpaper, batman sticker on back.",
            challenge_question="What is the wallpaper and sticker?",
        )

        self.found_item = Item.objects.create(
            reporter=self.finder,
            item_type="FOUND",
            title="Found Blue iPhone 14",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Found a blue encased smartphone on metro platform.",
            status="ACTIVE"
        )

        self.match = Match.objects.create(
            lost_item=self.lost_item,
            found_item=self.found_item,
            final_score=88.5,
            status="NOTIFIED",
        )

    def test_submit_claim_and_flow(self):
        # 1. Owner submits ownership claim (matches secrets closely -> AI score >= 70%)
        self.client.login(username="owner", password="password123")
        response = self.client.post(f"/claims/match/{self.match.id}/submit/", {
            "answer_text": "Wallpaper is my white husky dog, batman sticker on back.",
            "additional_info": "Lost around 6 PM.",
        })

        claim = OwnershipClaim.objects.get(match=self.match, claimant=self.owner)
        self.assertGreaterEqual(claim.ai_score, 70.0)
        self.assertTrue(claim.is_ai_verified)
        # Should be PENDING until finder confirms!
        self.assertEqual(claim.status, "PENDING")
        self.assertFalse(claim.finder_verified)
        self.assertEqual(claim.handover_otp, "")  # NO OTP released before finder confirms

        convo = Conversation.objects.get(match=self.match)
        self.assertEqual(convo.status, Conversation.STATUS_PENDING_FINDER)
        self.assertRedirects(response, f"/chat/{convo.id}/")

        # 2. Finder reviews chat and confirms the owner
        self.client.login(username="finder", password="password123")
        confirm_res = self.client.post(f"/chat/{convo.id}/confirm-owner/")
        self.assertRedirects(confirm_res, f"/chat/{convo.id}/")

        claim.refresh_from_db()
        convo.refresh_from_db()
        self.assertTrue(claim.finder_verified)
        self.assertEqual(claim.status, "ACCEPTED")
        self.assertEqual(len(claim.handover_otp), 6)  # OTP now generated!
        self.assertEqual(convo.status, Conversation.STATUS_ACTIVE)
        self.assertTrue(ReturnConfirmation.objects.filter(claim=claim).exists())

        # 3. Finder marks item as returned
        response = self.client.post(f"/claims/{claim.id}/return/")
        self.assertRedirects(response, "/dashboard/")
        rc = ReturnConfirmation.objects.get(claim=claim)
        self.assertTrue(rc.finder_confirmed)

        # 4. Owner confirms receipt
        self.client.login(username="owner", password="password123")
        response = self.client.post(f"/claims/{claim.id}/receipt/", {
            "confirmed": "yes"
        })
        self.assertRedirects(response, f"/claims/{claim.id}/success/")
        rc.refresh_from_db()
        self.assertTrue(rc.owner_confirmed)
        self.assertTrue(rc.is_complete())

        # Check item status resolved
        self.lost_item.refresh_from_db()
        self.found_item.refresh_from_db()
        self.assertEqual(self.lost_item.status, "RETURNED")
        self.assertFalse(self.lost_item.is_active)
        self.assertEqual(self.found_item.status, "RETURNED")
        self.assertFalse(self.found_item.is_active)

        # Check conversation is closed
        convo.refresh_from_db()
        self.assertFalse(convo.is_active)
        self.assertTrue(convo.is_closed)

        # Sending new message should be blocked
        chat_res = self.client.post(f"/chat/{convo.id}/send/", {"content": "Hello after close"})
        self.assertEqual(chat_res.status_code, 400)

    def test_ai_chat_verification_flow(self):
        # Create a fresh match
        lost2 = Item.objects.create(
            reporter=self.owner,
            item_type="LOST",
            title="Lost Wallet with Student ID",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Lost black leather wallet.",
            status="ACTIVE"
        )
        PrivateDetail.objects.create(
            item=lost2,
            hidden_info="Contains red metro card, 500 rupee note, and university library card.",
            challenge_question="What cards are inside the wallet?",
        )
        found2 = Item.objects.create(
            reporter=self.finder,
            item_type="FOUND",
            title="Found Leather Wallet",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Found a wallet near library.",
            status="ACTIVE"
        )
        match2 = Match.objects.create(
            lost_item=lost2,
            found_item=found2,
            final_score=85.0,
            status="NOTIFIED",
        )

        self.client.login(username="owner", password="password123")

        # 1. Start AI verification chat -> redirects to unified chat
        res = self.client.get(f"/claims/match/{match2.id}/submit/")
        convo2 = Conversation.objects.get(match=match2)
        self.assertRedirects(res, f"/chat/{convo2.id}/")
        self.assertEqual(convo2.status, Conversation.STATUS_AI_VERIFY)
        self.assertEqual(convo2.messages.filter(is_ai=True).count(), 1)  # Question 1 seeded

        claim2 = OwnershipClaim.objects.get(match=match2, claimant=self.owner)
        self.assertEqual(claim2.status, OwnershipClaim.STATUS_IN_PROGRESS)

        # 2. Answer Question 1
        res1 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "It is black leather with a red metro card and university library card."
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["convo_status"], Conversation.STATUS_AI_VERIFY)
        self.assertEqual(len(data1["messages"]), 2)  # User answer + AI Question 2

        # 3. Answer Question 2
        res2 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "Inside there is a 500 rupee note and small coin compartment."
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["convo_status"], Conversation.STATUS_AI_VERIFY)

        # 4. Answer Question 3
        res3 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "Brand is Wildcraft genuine leather."
        })
        self.assertEqual(res3.status_code, 200)

        # 5. Answer Question 4
        res4 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "Lost yesterday evening outside the central library gate around 5 PM."
        })
        self.assertEqual(res4.status_code, 200)

        # 6. Answer Question 5 (Final Step: photo/proof description) -> Triggers AI evaluation!
        res5 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "I have the purchase invoice and an old photo of the wallet with my library card."
        })
        self.assertEqual(res5.status_code, 200)
        data5 = res5.json()
        self.assertEqual(data5["convo_status"], Conversation.STATUS_PENDING_FINDER)

        claim2.refresh_from_db()
        convo2.refresh_from_db()
        self.assertTrue(claim2.is_ai_verified)
        self.assertGreaterEqual(claim2.ai_score, 70.0)
        self.assertEqual(claim2.status, OwnershipClaim.STATUS_PENDING)
        self.assertEqual(claim2.handover_otp, "")  # No OTP released yet
        self.assertEqual(convo2.status, Conversation.STATUS_PENDING_FINDER)

        # 7. Finder reviews chat and confirms owner -> releases OTP
        self.client.login(username="finder", password="password123")
        confirm_res = self.client.post(f"/chat/{convo2.id}/confirm-owner/")
        self.assertRedirects(confirm_res, f"/chat/{convo2.id}/")

        claim2.refresh_from_db()
        convo2.refresh_from_db()
        self.assertTrue(claim2.finder_verified)
        self.assertEqual(claim2.status, OwnershipClaim.STATUS_ACCEPTED)
        self.assertEqual(len(claim2.handover_otp), 6)  # OTP released!
        self.assertEqual(convo2.status, Conversation.STATUS_ACTIVE)


