import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0006_orderitem_sale_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckoutGroup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("currency", models.CharField(max_length=3)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("buyer_purchase_counted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkout_groups", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "checkout_groups",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="order",
            name="checkout_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="orders.checkoutgroup"),
        ),
    ]