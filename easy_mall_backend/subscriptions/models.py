import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SubscriptionPlan(models.Model):
    class Currency(models.TextChoices):
        CDF = "CDF", "CDF"
        USD = "USD", "USD"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, choices=Currency.choices)
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    features = models.JSONField(default=list, blank=True)
    limits = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plans"
        ordering = ["amount", "name"]
        indexes = [
            models.Index(fields=["is_active", "is_archived"], name="subplan_active_arch_idx")
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        ACTIVE = "active", _("Active")
        EXPIRED = "expired", _("Expirée")
        CANCELLED = "cancelled", _("Annulée")
        PAST_DUE = "past_due", _("Paiement en retard")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=SubscriptionPlan.Currency.choices)
    duration_days = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    subscribed_at = models.DateTimeField(default=timezone.now)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    next_payment_at = models.DateTimeField(null=True, blank=True)
    previous_subscription = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="renewals",
    )
    expiration_notice_sent_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        ordering = ["-subscribed_at"]
        indexes = [
            models.Index(
                fields=["user", "status", "expires_at"], name="sub_user_status_exp_idx"
            ),
            models.Index(fields=["status", "expires_at"], name="sub_status_exp_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.plan.name} ({self.get_status_display()})"


class SubscriptionSettings(models.Model):
    class PlanChangePolicy(models.TextChoices):
        DISABLED = "disabled", _("Désactivé")
        IMMEDIATE = "immediate", _("Après paiement, effet immédiat")
        AT_PERIOD_END = "at_period_end", _("Après paiement, à l'échéance")

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    plan_change_policy = models.CharField(
        max_length=20,
        choices=PlanChangePolicy.choices,
        default=PlanChangePolicy.DISABLED,
    )
    expiration_notice_days = models.PositiveSmallIntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_settings"

    def __str__(self):
        return "Règles globales d'abonnement"