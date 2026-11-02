from django.db import migrations


def approve_published_products(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(status="published", moderation_status="pending").update(
        moderation_status="approved"
    )


def reverse_approve_published_products(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(status="published", moderation_status="approved").update(
        moderation_status="pending"
    )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.RunPython(
            approve_published_products,
            reverse_code=reverse_approve_published_products,
        ),
    ]
