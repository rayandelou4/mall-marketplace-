from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_favorite_price_alert"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="productactivity",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterModelTable(
            name="productactivity",
            table="product_activities",
        ),
    ]