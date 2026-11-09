import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_backfill_stock_opening"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(max_length=100)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("stock_quantity", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variants", to="catalog.product")),
            ],
            options={
                "db_table": "product_variants",
                "ordering": ["label"],
            },
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(fields=("product", "label"), name="unique_product_variant_label"),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="variant",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="catalog.productvariant"),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="variant_label",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.CreateModel(
            name="ProductActivity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("activity_type", models.CharField(choices=[("view", "Consultation"), ("cart_add", "Ajout au panier")], max_length=12)),
                ("visitor_id", models.UUIDField()),
                ("event_id", models.UUIDField(unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="catalog.product")),
            ],
        ),
        migrations.AddIndex(
            model_name="productactivity",
            index=models.Index(fields=["product", "activity_type", "created_at"], name="product_activity_lookup_idx"),
        ),
        migrations.AddConstraint(
            model_name="productactivity",
            constraint=models.UniqueConstraint(condition=models.Q(activity_type="view"), fields=("product", "activity_type", "visitor_id"), name="unique_product_viewer"),
        ),
    ]
