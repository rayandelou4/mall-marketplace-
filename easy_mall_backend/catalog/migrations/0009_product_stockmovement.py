import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0008_product_sale_method"),
        ("orders", "0007_checkout_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_title", models.CharField(max_length=150)),
                ("movement_type", models.CharField(choices=[("opening", "Stock initial"), ("adjustment", "Ajustement vendeur"), ("sale", "Commande"), ("cancellation", "Annulation")], max_length=20)),
                ("quantity_delta", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="orders.order")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="catalog.product")),
            ],
            options={
                "db_table": "stock_movements",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["product", "created_at"], name="stock_movement_product_idx"),
        ),
    ]