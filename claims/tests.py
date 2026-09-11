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

        # 3. Answer Question 2 with matching confidential details -> Verifies early in 2 questions!
        res2 = self.client.post(f"/chat/{convo2.id}/send/", {
            "content": "Inside there is a 500 rupee note and small coin compartment."
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["convo_status"], Conversation.STATUS_PENDING_FINDER)

        claim2.refresh_from_db()
        convo2.refresh_from_db()
        self.assertTrue(claim2.is_ai_verified)
        self.assertGreaterEqual(claim2.ai_score, 75.0)
        self.assertEqual(claim2.status, OwnershipClaim.STATUS_PENDING)
        self.assertEqual(claim2.handover_otp, "")  # No OTP released yet
        self.assertEqual(convo2.status, Conversation.STATUS_PENDING_FINDER)

        # 4. Finder reviews chat and confirms owner -> releases OTP
        self.client.login(username="finder", password="password123")
        confirm_res = self.client.post(f"/chat/{convo2.id}/confirm-owner/")
        self.assertRedirects(confirm_res, f"/chat/{convo2.id}/")

        claim2.refresh_from_db()
        convo2.refresh_from_db()
        self.assertTrue(claim2.finder_verified)
        self.assertEqual(claim2.status, OwnershipClaim.STATUS_ACCEPTED)
        self.assertEqual(len(claim2.handover_otp), 6)  # OTP released!
        self.assertEqual(convo2.status, Conversation.STATUS_ACTIVE)

    def test_ai_chat_verification_adaptive_needs_more_questions(self):
        # Create an item requiring multiple questions because claimant gives partial info
        lost3 = Item.objects.create(
            reporter=self.owner,
            item_type="LOST",
            title="Lost Laptop Backpack",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Lost gray backpack.",
            status="ACTIVE"
        )
        PrivateDetail.objects.create(
            item=lost3,
            hidden_info="Secret compartment with silver macbook air and purple keychain.",
            challenge_question="What is hidden inside the secret compartment?",
        )
        found3 = Item.objects.create(
            reporter=self.finder,
            item_type="FOUND",
            title="Found Backpack",
            category=self.cat,
            city="Delhi",
            date_event=timezone.now().date(),
            description="Found gray backpack on bench.",
            status="ACTIVE"
        )
        match3 = Match.objects.create(
            lost_item=lost3,
            found_item=found3,
            final_score=80.0,
            status="NOTIFIED",
        )

        self.client.login(username="owner", password="password123")
        self.client.get(f"/claims/match/{match3.id}/submit/")
        convo3 = Conversation.objects.get(match=match3)

        # Answer 1: Vague
        r1 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "It is gray color."})
        self.assertEqual(r1.json()["convo_status"], Conversation.STATUS_AI_VERIFY)

        # Answer 2: Still partial (not >= 75%)
        r2 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "It has 3 zippers."})
        self.assertEqual(r2.json()["convo_status"], Conversation.STATUS_AI_VERIFY)

        # Answer 3: Still partial
        r3 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "Lost yesterday."})
        self.assertEqual(r3.json()["convo_status"], Conversation.STATUS_AI_VERIFY)

        # Answer 4: Still partial
        r4 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "Carried a water bottle."})
        self.assertEqual(r4.json()["convo_status"], Conversation.STATUS_AI_VERIFY)

        # Answer 5: Still partial -> leads to Question 6
        r5 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "Has a front organizer."})
        self.assertEqual(r5.json()["convo_status"], Conversation.STATUS_AI_VERIFY)

        # Answer 6: Provides secret details at step 6
        r6 = self.client.post(f"/chat/{convo3.id}/send/", {"content": "Secret compartment has silver macbook air and purple keychain."})
        self.assertEqual(r6.json()["convo_status"], Conversation.STATUS_PENDING_FINDER)

        claim3 = OwnershipClaim.objects.get(match=match3, claimant=self.owner)
        self.assertTrue(claim3.is_ai_verified)
        self.assertGreaterEqual(claim3.ai_score, 75.0)

    def test_ai_scoring_genuine_owner_fairness(self):
        from claims.ai_verifier import evaluate_claim_ownership
        # Genuine owner who provides key secret details using conversational wording
        res = evaluate_claim_ownership(
            lost_item=self.lost_item,
            claimant_answer="I have a batman sticker on the back and dog wallpaper of my husky.",
            claimant_notes="Lost at Rajiv Chowk."
        )
        self.assertTrue(res["is_verified"])
        self.assertGreaterEqual(res["match_score"], 75.0)
        self.assertEqual(res["confidence"], "HIGH")

    def test_ai_scoring_scammer_rejection(self):
        from claims.ai_verifier import evaluate_claim_ownership
        # Scammer giving vague generic guesses
        res = evaluate_claim_ownership(
            lost_item=self.lost_item,
            claimant_answer="Please return my phone, I lost it yesterday and it is very important to me.",
            claimant_notes="It was a gift."
        )
        self.assertFalse(res["is_verified"])
        self.assertLess(res["match_score"], 40.0)
        self.assertEqual(res["confidence"], "LOW")

    def test_dynamic_question_adaptive_flow(self):
        from claims.ai_verifier import generate_ai_interview_question
        # Question 1 asks challenge question
        q1 = generate_ai_interview_question(self.lost_item, [], 1)
        self.assertIn("wallpaper", q1.lower())

        # Question 2 asks about wallpaper / contents
        q2 = generate_ai_interview_question(self.lost_item, [{"role": "user", "content": "Blue case"}], 2)
        self.assertTrue(len(q2) > 10)

        # Question 6 asks for proof
        q6 = generate_ai_interview_question(self.lost_item, [], 6)
        self.assertIn("proof", q6.lower())


