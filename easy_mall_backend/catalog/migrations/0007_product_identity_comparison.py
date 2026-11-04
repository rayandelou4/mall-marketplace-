import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_suspension"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductIdentity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=180)),
                ("brand", models.CharField(blank=True, max_length=100)),
                ("model_name", models.CharField(blank=True, max_length=150)),
                (
                    "manufacturer_reference",
                    models.CharField(blank=True, max_length=100),
                ),
                ("variant", models.CharField(blank=True, max_length=150)),
                ("comparison_key", models.CharField(editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_identities",
                        to="catalog.category",
                    ),
                ),
            ],
            options={
                "db_table": "product_identities",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="comparison_identity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="offers",
                to="catalog.productidentity",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=[
                    "comparison_identity",
                    "currency",
                    "status",
                    "moderation_status",
                ],
                name="product_cmp_group_idx",
            ),
        ),
    ]