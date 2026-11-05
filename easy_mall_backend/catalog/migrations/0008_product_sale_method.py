from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_product_identity_comparison"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sale_method",
            field=models.CharField(
                choices=[("delivery", "Livraison"), ("pickup", "Remise en main propre")],
                default="delivery",
                max_length=10,
            ),
        ),
    ]