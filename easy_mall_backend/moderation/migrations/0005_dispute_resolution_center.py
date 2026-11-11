import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moderation", "0004_messagereport_accountmoderationaction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="dispute",
            name="reason",
            field=models.CharField(
                choices=[
                    ("not_received", "Produit non reçu"),
                    ("damaged_item", "Produit endommagé"),
                    ("not_as_described", "Produit différent de la description"),
                    ("counterfeit_suspected", "Produit contrefait ou suspect"),
                    ("seller_fraud", "Vendeur frauduleux"),
                    ("other", "Autre problème lié à la transaction"),
                ],
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="dispute",
            name="appeal_deadline",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dispute",
            name="appealed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dispute",
            name="refund_status",
            field=models.CharField(
                choices=[
                    ("not_applicable", "Non applicable"),
                    ("pending", "À traiter"),
                    ("processing", "En cours"),
                    ("completed", "Confirmé"),
                    ("failed", "Échec"),
                ],
                default="not_applicable",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="dispute",
            name="refund_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="dispute",
            name="refund_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.CreateModel(
            name="DisputeMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("message", "Message"), ("appeal", "Contestation"), ("decision", "Décision")], default="message", max_length=12)),
                ("body", models.TextField()),
                ("evidence", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dispute_messages", to=settings.AUTH_USER_MODEL)),
                ("dispute", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="moderation.dispute")),
            ],
            options={"db_table": "dispute_messages", "ordering": ["created_at", "id"]},
        ),
        migrations.AlterField(
            model_name="accountmoderationaction",
            name="action",
            field=models.CharField(
                choices=[("warning", "Avertissement"), ("suspended", "Compte suspendu"), ("reinstated", "Compte rétabli")],
                max_length=12,
            ),
        ),
    ]