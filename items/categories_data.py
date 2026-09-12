from django.utils.text import slugify

DEFAULT_CATEGORIES = [
    ("Electronics & Gadgets", "\U0001F4F1", "Laptops, smartphones, headphones, tablets, smartwatches, chargers"),
    ("Wallets & Purses", "\U0001F45B", "Leather wallets, card holders, coin purses, clutches"),
    ("Govt IDs & Cards", "\U0001F194", "Aadhaar, PAN cards, Driving Licenses, Voter IDs, ATM/Debit cards"),
    ("Bags & Luggage", "\U0001F392", "Backpacks, duffle bags, suitcases, messenger bags"),
    ("Keys & Keychains", "\U0001F511", "House keys, car fobs, bike keys, lock combinations"),
    ("Watches & Jewelry", "\u231A", "Wristwatches, rings, chains, bracelets, earrings"),
    ("Documents & Books", "\U0001F4C4", "Passports, certificates, college files, books, diaries"),
    ("Clothing & Eyewear", "\U0001F455", "Jackets, sweaters, sunglasses, prescription glasses, caps"),
    ("Others & Miscellaneous", "\U0001F4E6", "Water bottles, umbrellas, musical instruments, sports gear"),
]


def auto_seed_categories():
    """Ensures all default categories are pre-listed in the database."""
    from items.models import Category
    try:
        for name, icon, desc in DEFAULT_CATEGORIES:
            Category.objects.get_or_create(
                name=name,
                defaults={
                    "slug": slugify(name),
                    "icon": icon,
                    "description": desc,
                }
            )
    except Exception:
        pass
