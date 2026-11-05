from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_order_shipping_address_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="sale_method",
            field=models.CharField(
                choices=[("delivery", "Livraison"), ("pickup", "Remise en main propre")],
                default="delivery",
                max_length=10,
            ),
        ),
    ]