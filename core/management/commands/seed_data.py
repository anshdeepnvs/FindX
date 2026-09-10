from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from items.models import Category, Item

User = get_user_model()


class Command(BaseCommand):
    help = "Seed database with initial categories, demo users, and sample lost & found items."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Seeding categories..."))
        categories_data = [
            ("Electronics & Gadgets", "📱", "Laptops, smartphones, headphones, tablets, smartwatches, chargers"),
            ("Wallets & Purses", "👛", "Leather wallets, card holders, coin purses, clutches"),
            ("Govt IDs & Cards", "🆔", "Aadhaar, PAN cards, Driving Licenses, Voter IDs, ATM/Debit cards"),
            ("Bags & Luggage", "🎒", "Backpacks, duffle bags, suitcases, messenger bags"),
            ("Keys & Keychains", "🔑", "House keys, car fobs, bike keys, lock combinations"),
            ("Watches & Jewelry", "⌚", "Wristwatches, rings, chains, bracelets, earrings"),
            ("Documents & Books", "📄", "Passports, certificates, college files, books, diaries"),
            ("Clothing & Eyewear", "👕", "Jackets, sweaters, sunglasses, prescription glasses, caps"),
            ("Others & Miscellaneous", "📦", "Water bottles, umbrellas, musical instruments, sports gear"),
        ]

        cats_map = {}
        for name, icon, desc in categories_data:
            cat, _ = Category.objects.get_or_create(
                name=name,
                defaults={"icon": icon, "description": desc}
            )
            cats_map[name] = cat
        self.stdout.write(self.style.SUCCESS(f"Created/verified {len(cats_map)} categories."))

        # Demo Users
        self.stdout.write(self.style.NOTICE("Creating demo accounts..."))
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@lostandfound.local", "is_staff": True, "is_superuser": True, "is_email_verified": True}
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()

        finder_user, created = User.objects.get_or_create(
            username="priya_finder",
            defaults={"email": "priya@example.com", "is_email_verified": True, "trust_score": 110}
        )
        if created:
            finder_user.set_password("testpass123")
            finder_user.save()

        claimant_user, created = User.objects.get_or_create(
            username="rahul_owner",
            defaults={"email": "rahul@example.com", "is_email_verified": True, "trust_score": 100}
        )
        if created:
            claimant_user.set_password("testpass123")
            claimant_user.save()

        self.stdout.write(self.style.SUCCESS("Demo accounts ready (admin / admin123, priya_finder / testpass123, rahul_owner / testpass123)."))

        # Seed Items
        self.stdout.write(self.style.NOTICE("Creating sample listings with anti-scam private fields..."))

        today = timezone.now().date()

        # Item 1: Found Wallet with secret cards & photo
        Item.objects.get_or_create(
            title="Brown Leather Men's Wallet found at Metro Station",
            reporter=finder_user,
            defaults={
                "item_type": "FOUND",
                "category": cats_map["Wallets & Purses"],
                "city": "New Delhi",
                "location_details": "Rajiv Chowk Metro Station, Platform 2 near ticket counter",
                "date_lost_or_found": today - timedelta(days=2),
                "primary_color": "Brown",
                "brand": "Wildhorn",
                "public_description": "Found a genuine brown leather wallet left on a bench. The wallet has several card slots and appears recently dropped. Safe with metro security.",
                "hidden_details": (
                    "Contains an SBI Global Debit Card ending in 4102, a college student ID for Delhi University "
                    "(Roll no 21045), a Rs 500 currency note, and a small passport photo of an elderly couple."
                ),
                "challenge_question": "What bank card is inside, what are the last digits, and what photo or cash is in the slot?",
                "status": "OPEN",
            }
        )

        # Item 2: Found MacBook with secret sticker & wallpaper
        Item.objects.get_or_create(
            title="Apple MacBook Air 13-inch in Dark Sleeve",
            reporter=finder_user,
            defaults={
                "item_type": "FOUND",
                "category": cats_map["Electronics & Gadgets"],
                "city": "Mumbai",
                "location_details": "Chhatrapati Shivaji Maharaj International Airport (T2 Departure Lounge)",
                "date_lost_or_found": today - timedelta(days=1),
                "primary_color": "Silver",
                "brand": "Apple",
                "public_description": "Found a silver 13-inch Apple laptop in a padded grey zipper case near Gate 42 charging station.",
                "hidden_details": (
                    "Laptop lid has a circular yellow NASA sticker on the top-left. There is a slight scratch near the headphone jack. "
                    "Lockscreen wallpaper is a golden retriever puppy sitting on grass."
                ),
                "challenge_question": "Describe the sticker on the lid, any scratch marks, and what photo is set as the lockscreen wallpaper.",
                "status": "OPEN",
            }
        )

        # Item 3: Lost Headphones
        Item.objects.get_or_create(
            title="Lost Bose QuietComfort 45 Noise Cancelling Headphones",
            reporter=claimant_user,
            defaults={
                "item_type": "LOST",
                "category": cats_map["Electronics & Gadgets"],
                "city": "Bengaluru",
                "location_details": "Indiranagar 100 Feet Road cafe",
                "date_lost_or_found": today - timedelta(days=3),
                "primary_color": "Black",
                "brand": "Bose",
                "public_description": "Lost my matte black Bose QC45 headphones in their original hard travel case. Please contact me if found!",
                "hidden_details": "Right earcup padding has a tiny fingernail tear. Inside case has an extra aux cable with silver 3.5mm adapter.",
                "status": "OPEN",
            }
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with realistic anti-scam items!"))
