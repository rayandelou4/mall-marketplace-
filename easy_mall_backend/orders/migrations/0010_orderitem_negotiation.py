import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("negotiations", "0001_initial"),
        ("orders", "0009_orderitem_promotion_loyalty"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="negotiation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="negotiations.negotiation",
            ),
        ),
    ]