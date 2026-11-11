from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0011_product_variants_and_activity")]

    operations = [
        migrations.AddField(
            model_name="favorite",
            name="target_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="favorite",
            name="last_notified_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]