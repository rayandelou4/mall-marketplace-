import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0008_user_show_phone_on_listings"),
        ("catalog", "0011_product_variants_and_activity"),
    ]

    operations = [
        migrations.CreateModel(
            name="Negotiation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("open", "En cours"), ("accepted", "Acceptée, à commander"), ("rejected", "Refusée"), ("expired", "Expirée"), ("completed", "Commandée")], default="open", max_length=12)),
                ("accepted_price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("expires_at", models.DateTimeField()),
                ("reserved_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="price_negotiations_as_buyer", to=settings.AUTH_USER_MODEL)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="negotiations", to="catalog.product")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="price_negotiations_as_seller", to=settings.AUTH_USER_MODEL)),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="negotiations", to="catalog.productvariant")),
            ],
            options={"db_table": "price_negotiations", "ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="NegotiationEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("proposal", "Proposition"), ("counter_proposal", "Contre-proposition"), ("accepted", "Acceptation"), ("rejected", "Refus"), ("expired", "Expiration"), ("checkout", "Commande créée")], max_length=20)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="negotiation_events", to=settings.AUTH_USER_MODEL)),
                ("negotiation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="negotiations.negotiation")),
            ],
            options={"db_table": "negotiation_events", "ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="negotiation",
            index=models.Index(fields=["status", "expires_at"], name="price_neg_statu_6f8cd2_idx"),
        ),
    ]