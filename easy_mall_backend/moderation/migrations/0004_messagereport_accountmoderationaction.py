import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_user_suspension"),
        ("messaging", "0007_message_voice_url"),
        ("moderation", "0003_moderation_evidence_history"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountModerationAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("suspended", "Compte suspendu"), ("reinstated", "Compte rétabli")], max_length=12)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="account_moderation_actions", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderation_history", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "account_moderation_actions", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MessageReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reported_username", models.CharField(max_length=50)),
                ("message_snapshot", models.JSONField(blank=True, default=dict)),
                ("reason", models.CharField(choices=[("threat", "Menace"), ("inappropriate", "Message inapproprié"), ("harassment", "Harcèlement"), ("fraud", "Fraude ou tentative d'arnaque"), ("other", "Autre motif")], max_length=24)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("new", "Nouveau"), ("under_review", "En cours d'examen"), ("valid", "Fondé"), ("rejected", "Rejeté"), ("closed", "Clôturé")], default="new", max_length=20)),
                ("review_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="message_reports", to="messaging.conversation")),
                ("message", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reports", to="messaging.message")),
                ("reported_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="message_reports_received", to=settings.AUTH_USER_MODEL)),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="message_reports_filed", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="message_reports_reviewed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "message_reports", "ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="messagereport",
            constraint=models.UniqueConstraint(condition=models.Q(status__in=["new", "under_review", "valid"]), fields=("message", "reporter"), name="unique_active_message_report_per_user"),
        ),
    ]