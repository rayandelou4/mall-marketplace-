from django.db import migrations


def approve_archived_products(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(status="archived", moderation_status="pending").update(
        moderation_status="approved"
    )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_approve_published_products")]

    operations = [migrations.RunPython(approve_archived_products, migrations.RunPython.noop)]