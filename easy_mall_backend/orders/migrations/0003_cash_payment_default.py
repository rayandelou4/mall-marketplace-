from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_payment_method_orderitem_is_shipped"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[("cash", "Espèces à la réception"), ("mobile_money", "Mobile Money")],
                default="cash",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "En attente de remise"),
                    ("paid", "Payée"),
                    ("shipped", "Expédiée"),
                    ("delivered", "Livrée"),
                    ("cancelled", "Annulée"),
                    ("disputed", "En litige"),
                    ("refunded", "Remboursée"),
                ],
                default="pending",
                max_length=12,
            ),
        ),
    ]