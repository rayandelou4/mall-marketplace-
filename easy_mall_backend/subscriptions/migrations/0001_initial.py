import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(0)])),
                ("currency", models.CharField(choices=[("CDF", "CDF"), ("USD", "USD")], max_length=3)),
                ("duration_days", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("features", models.JSONField(blank=True, default=list)),
                ("limits", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=False)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "subscription_plans",
                "ordering": ["amount", "name"],
                "indexes": [models.Index(fields=["is_active", "is_archived"], name="subplan_active_arch_idx")],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("plan_change_policy", models.CharField(choices=[("disabled", "Désactivé"), ("immediate", "Après paiement, effet immédiat"), ("at_period_end", "Après paiement, à l'échéance")], default="disabled", max_length=20)),
                ("expiration_notice_days", models.PositiveSmallIntegerField(default=3)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "subscription_settings"},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_paid", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(choices=[("CDF", "CDF"), ("USD", "USD")], max_length=3)),
                ("duration_days", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("pending", "En attente"), ("active", "Active"), ("expired", "Expirée"), ("cancelled", "Annulée"), ("past_due", "Paiement en retard")], default="pending", max_length=12)),
                ("subscribed_at", models.DateTimeField(default=timezone.now)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("auto_renew", models.BooleanField(default=False)),
                ("next_payment_at", models.DateTimeField(blank=True, null=True)),
                ("expiration_notice_sent_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="subscriptions.subscriptionplan")),
                ("previous_subscription", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="renewals", to="subscriptions.subscription")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "subscriptions",
                "ordering": ["-subscribed_at"],
                "indexes": [
                    models.Index(fields=["user", "status", "expires_at"], name="sub_user_status_exp_idx"),
                    models.Index(fields=["status", "expires_at"], name="sub_status_exp_idx"),
                ],
            },
        ),
    ]