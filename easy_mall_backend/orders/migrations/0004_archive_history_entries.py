from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_cash_payment_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="hidden_by_buyer",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="hidden_by_seller",
            field=models.BooleanField(default=False),
        ),
    ]