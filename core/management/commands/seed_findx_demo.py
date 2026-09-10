from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from items.models import Item, Category, PrivateDetail
from matching.models import Match
from claims.models import OwnershipClaim, ReturnConfirmation
from chat.models import Conversation, Message
from notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds comprehensive demo data for FindX hackathon presentation"

    def handle(self, *args, **options):
        self.stdout.write("Seeding FindX demo data...")

        # 1. Users
        users_data = [
            ("rahul_owner", "rahul@example.com", "Rahul Sharma", "+919876543211"),
            ("priya_finder", "priya@example.com", "Priya Patel", "+919876543212"),
            ("ananya_lost", "ananya@example.com", "Ananya Verma", "+919876543213"),
            ("vikram_found", "vikram@example.com", "Vikram Malhotra", "+919876543214"),
        ]
        users = {}
        for username, email, full_name, phone in users_data:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": full_name.split()[0],
                    "last_name": full_name.split()[1],
                    "phone_number": phone,
                    "is_email_verified": True,
                    "trust_score": 115,
                }
            )
            if created:
                u.set_password("testpass123")
                u.save()
            users[username] = u

        # 2. Categories
        cat_elec, _ = Category.objects.get_or_create(name="Electronics & Gadgets", defaults={"icon": "📱"})
        cat_bag, _  = Category.objects.get_or_create(name="Bags, Backpacks & Luggage", defaults={"icon": "🎒"})
        cat_doc, _  = Category.objects.get_or_create(name="Documents, Cards & IDs", defaults={"icon": "📄"})
        cat_key, _  = Category.objects.get_or_create(name="Keys & Keychains", defaults={"icon": "🔑"})

        today = timezone.now().date()

        # 3. Item Pair 1: Blue Backpack (High AI match 92%)
        lost_bag, _ = Item.objects.get_or_create(
            title="Navy Blue Wildcraft Laptop Backpack",
            reporter=users["rahul_owner"],
            defaults={
                "item_type": "LOST",
                "category": cat_bag,
                "brand": "Wildcraft",
                "color": "Navy Blue",
                "city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
                "location_name": "MG Road Metro Station",
                "date_event": today - timedelta(days=2),
                "description": "Navy blue Wildcraft 32L backpack with orange zipper pulls. Contains my work laptop and tech accessories.",
                "status": "MATCH_FOUND",
            }
        )
        PrivateDetail.objects.get_or_create(
            item=lost_bag,
            defaults={
                "hidden_info": "Dell Inspiron laptop with a Python sticker on lid. Keychain with a miniature Eiffel Tower inside front mesh pocket.",
                "challenge_question": "What sticker is on the laptop and what is in the front mesh pocket?",
                "serial_hint": "DELL-CN-9021",
            }
        )

        found_bag, _ = Item.objects.get_or_create(
            title="Dark Blue Wildcraft Bag with Laptop",
            reporter=users["priya_finder"],
            defaults={
                "item_type": "FOUND",
                "category": cat_bag,
                "brand": "Wildcraft",
                "color": "Navy Blue",
                "city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
                "location_name": "MG Road Metro Exit 2 bench",
                "date_event": today - timedelta(days=2),
                "description": "Found a dark navy Wildcraft backpack left unattended near ticket gate. Seems to contain a computer inside.",
                "status": "CLAIM_PENDING",
            }
        )

        # Match 1
        match1, _ = Match.objects.get_or_create(
            lost_item=lost_bag,
            found_item=found_bag,
            defaults={
                "image_score": 0.88,
                "text_score": 0.94,
                "category_score": 1.0,
                "color_score": 1.0,
                "location_score": 1.0,
                "date_score": 1.0,
                "final_score": 94.2,
                "status": "ACCEPTED",
            }
        )

        # Claim 1 (Accepted -> Chat Open)
        claim1, _ = OwnershipClaim.objects.get_or_create(
            match=match1,
            claimant=users["rahul_owner"],
            defaults={
                "status": "ACCEPTED",
                "answer_text": "The laptop inside has a bright yellow Python logo sticker on the lid. The front mesh pocket has a metallic miniature Eiffel Tower keychain.",
                "additional_info": "I can bring my college ID to match when we meet at the metro security counter.",
                "handover_otp": "749201",
            }
        )
        ReturnConfirmation.objects.get_or_create(claim=claim1)

        convo1, _ = Conversation.objects.get_or_create(
            match=match1,
            defaults={
                "participant_a": users["rahul_owner"],
                "participant_b": users["priya_finder"],
            }
        )
        if convo1.messages.count() == 0:
            Message.objects.create(
                conversation=convo1,
                sender=users["priya_finder"],
                content="Hello Rahul! Your answer matches the laptop and keychain perfectly. Where can we safely meet?",
            )
            Message.objects.create(
                conversation=convo1,
                sender=users["rahul_owner"],
                content="Hi Priya! Thank you so much! Can we meet tomorrow at 11 AM near the MG Road Metro Station customer helpdesk?",
            )
            Message.objects.create(
                conversation=convo1,
                sender=users["priya_finder"],
                content="Sure, 11 AM works well. I'll verify the 6-digit OTP code with you then.",
            )

        # Notifications
        Notification.objects.get_or_create(
            user=users["rahul_owner"],
            title="🎉 Ownership Claim Approved!",
            defaults={
                "notif_type": "CLAIM",
                "body": "Priya accepted your claim for 'Navy Blue Wildcraft Laptop Backpack'. Safe chat is now unlocked!",
                "link": f"/chat/{convo1.id}/",
                "is_read": False,
            }
        )

        # 4. Item Pair 2: Car Key Fob (78% match)
        lost_key, _ = Item.objects.get_or_create(
            title="Hyundai Smart Car Key Fob",
            reporter=users["ananya_lost"],
            defaults={
                "item_type": "LOST",
                "category": cat_key,
                "brand": "Hyundai",
                "color": "Black / Silver",
                "city": "Mumbai",
                "state": "Maharashtra",
                "country": "India",
                "location_name": "Phoenix Palladium Mall Food Court",
                "date_event": today - timedelta(days=1),
                "description": "Black Hyundai Creta smart key fob with a red leather loop.",
                "status": "MATCH_FOUND",
            }
        )
        PrivateDetail.objects.get_or_create(
            item=lost_key,
            defaults={
                "hidden_info": "A silver charm with letter 'A' engraved on the back of the red loop.",
                "challenge_question": "What letter or initial is on the key charm?",
            }
        )

        found_key, _ = Item.objects.get_or_create(
            title="Car Remote Key with Red Strap",
            reporter=users["vikram_found"],
            defaults={
                "item_type": "FOUND",
                "category": cat_key,
                "brand": "Hyundai",
                "color": "Black",
                "city": "Mumbai",
                "state": "Maharashtra",
                "country": "India",
                "location_name": "Lower Parel Parking Level 2",
                "date_event": today - timedelta(days=1),
                "description": "Found a Hyundai electronic car key with a red strap near parking elevator.",
                "status": "ACTIVE",
            }
        )

        Match.objects.get_or_create(
            lost_item=lost_key,
            found_item=found_key,
            defaults={
                "image_score": 0.75,
                "text_score": 0.85,
                "category_score": 1.0,
                "color_score": 0.8,
                "location_score": 1.0,
                "date_score": 1.0,
                "final_score": 86.0,
                "status": "NOTIFIED",
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded FindX demo data with users, categories, matching pairs, and chat conversations!"))
