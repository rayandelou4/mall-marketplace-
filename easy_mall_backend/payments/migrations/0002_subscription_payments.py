import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentprovider",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="paymentprovider",
            name="adapter_path",
            field=models.CharField(blank=True, help_text="Chemin Python de l'adaptateur serveur; les secrets restent dans l'environnement.", max_length=255),
        ),
        migrations.AlterField(
            model_name="payment",
            name="order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="orders.order"),
        ),
        migrations.AddField(
            model_name="payment",
            name="subscription",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="subscriptions.subscription"),
        ),
        migrations.AddField(
            model_name="payment",
            name="external_reference",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="payment",
            name="idempotency_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(choices=[("pending", "En attente"), ("held_escrow", "Retenu (escrow)"), ("completed", "Complété"), ("successful", "Réussi"), ("failed", "Échoué"), ("refunded", "Remboursé")], default="pending", max_length=12),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=(Q(order__isnull=False, subscription__isnull=True) | Q(order__isnull=True, subscription__isnull=False)), name="payment_single_commercial_subject"),
        ),
        migrations.CreateModel(
            name="PaymentWebhookEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("external_event_id", models.CharField(max_length=150)),
                ("event_type", models.CharField(blank=True, max_length=80)),
                ("payload_sha256", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("received", "Reçu"), ("processed", "Traité"), ("rejected", "Rejeté")], default="received", max_length=12)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="webhook_events", to="payments.payment")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="webhook_events", to="payments.paymentprovider")),
            ],
            options={"db_table": "payment_webhook_events", "ordering": ["-received_at"]},
        ),
        migrations.AddConstraint(
            model_name="paymentwebhookevent",
            constraint=models.UniqueConstraint(fields=("provider", "external_event_id"), name="unique_provider_webhook_event"),
        ),
    ]