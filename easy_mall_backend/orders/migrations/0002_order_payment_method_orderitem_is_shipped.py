from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[("cash", "Espèces à la réception"), ("mobile_money", "Mobile Money")],
                default="mobile_money",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="is_shipped",
            field=models.BooleanField(default=False),
        ),
    ]