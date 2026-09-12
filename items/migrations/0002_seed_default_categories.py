from django.db import migrations
from django.utils.text import slugify
from items.categories_data import DEFAULT_CATEGORIES

def seed_categories(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    for name, icon, desc in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "icon": icon,
                "description": desc,
            }
        )

def unseed_categories(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
