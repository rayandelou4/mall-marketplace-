"""
Modèles de l'app `payments`.

Implémente le pattern Adapter décrit au §8 du document d'architecture :
`PaymentProvider` référence les moyens de paiement disponibles par marché
(Mobile Money par pays, cartes, wallet interne), et `Payment` porte le cycle
de vie escrow (fonds retenus jusqu'à confirmation de réception par l'acheteur).
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

DEFAULT_ESCROW_HOLD_DAYS = 7


class SupportedMarket(models.Model):
    """Pays où Mall est disponible, avec sa devise — clé du multi-pays africain."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country_code = models.CharField(max_length=2, unique=True, help_text="Code ISO 3166-1 alpha-2, ex. CD")
    country_name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3, help_text="Code ISO 4217, ex. CDF, USD")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "supported_markets"
        verbose_name = _("marché supporté")
        verbose_name_plural = _("marchés supportés")
        ordering = ["country_name"]

    def __str__(self):
        return f"{self.country_name} ({self.currency_code})"


class PaymentProvider(models.Model):
    """Moyen de paiement concret disponible sur un marché (ou global pour Stripe/PayPal)."""

    class ProviderType(models.TextChoices):
        MOBILE_MONEY = "mobile_money", _("Mobile Money")
        CARD = "card", _("Carte bancaire")
        WALLET = "wallet", _("Portefeuille interne")
        EXTERNAL = "external", _("Passerelle externe")

    class Code(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        ORANGE_MONEY = "orange_money", "Orange Money"
        AIRTEL_MONEY = "airtel_money", "Airtel Money"
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        CARD = "card", _("Carte bancaire")
        WALLET = "wallet", _("Portefeuille interne")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, choices=Code.choices)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    # null = disponible globalement (Stripe, PayPal) plutôt que lié à un seul pays.
    market = models.ForeignKey(
        SupportedMarket,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payment_providers",
    )
    is_active = models.BooleanField(default=True)
    adapter_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Chemin Python de l'adaptateur serveur; les secrets restent dans l'environnement.",
    )

    class Meta:
        db_table = "payment_providers"
        verbose_name = _("moyen de paiement")
        verbose_name_plural = _("moyens de paiement")
        constraints = [
            models.UniqueConstraint(fields=["code", "market"], name="unique_provider_per_market")
        ]

    def __str__(self):
        market = self.market.country_name if self.market else _("Global")
        return f"{self.get_code_display()} — {market}"


class Wallet(models.Model):
    """Portefeuille électronique interne d'un utilisateur (ventes créditées, achats débités)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wallets"
        verbose_name = _("portefeuille")
        verbose_name_plural = _("portefeuilles")

    def __str__(self):
        return f"Wallet de {self.user} — {self.balance} {self.currency}"

    def credit(self, amount):
        """Crédite le solde de façon atomique (F() évite les conditions de course)."""
        Wallet.objects.filter(pk=self.pk).update(
            balance=models.F("balance") + amount, updated_at=timezone.now()
        )
        self.refresh_from_db(fields=["balance", "updated_at"])

    def debit(self, amount):
        if amount > self.balance:
            raise ValueError("Solde insuffisant pour ce débit.")
        Wallet.objects.filter(pk=self.pk).update(
            balance=models.F("balance") - amount, updated_at=timezone.now()
        )
        self.refresh_from_db(fields=["balance", "updated_at"])


class Payment(models.Model):
    """
    Paiement lié à une commande, avec cycle de vie escrow (§8) :
    pending → held_escrow (fonds retenus) → completed (libérés au vendeur) / refunded.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        HELD_ESCROW = "held_escrow", _("Retenu (escrow)")
        COMPLETED = "completed", _("Complété")
        SUCCESSFUL = "successful", _("Réussi")
        FAILED = "failed", _("Échoué")
        REFUNDED = "refunded", _("Remboursé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments",
        null=True, blank=True,
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription", on_delete=models.PROTECT,
        related_name="payments", null=True, blank=True,
    )
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    transaction_reference = models.CharField(max_length=100, unique=True)
    external_reference = models.CharField(max_length=150, blank=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # Date de libération automatique des fonds au vendeur si l'acheteur ne
    # confirme pas la réception avant (job Celery Beat périodique — §8).
    escrow_release_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        verbose_name = _("paiement")
        verbose_name_plural = _("paiements")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "escrow_release_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(order__isnull=False, subscription__isnull=True)
                    | Q(order__isnull=True, subscription__isnull=False)
                ),
                name="payment_single_commercial_subject",
            ),
        ]

    def __str__(self):
        return f"Paiement {self.transaction_reference} — {self.get_status_display()}"

    def mark_held_escrow(self, hold_days=DEFAULT_ESCROW_HOLD_DAYS):
        """À appeler quand le fournisseur confirme la réception des fonds."""
        self.status = self.Status.HELD_ESCROW
        self.confirmed_at = timezone.now()
        self.escrow_release_at = timezone.now() + timedelta(days=hold_days)
        self.save(update_fields=["status", "confirmed_at", "escrow_release_at"])

    def release_to_seller(self):
        """Libère les fonds : crédite le(s) wallet(s) vendeur, moins la commission."""
        if self.status != self.Status.HELD_ESCROW:
            raise ValueError("Seul un paiement en escrow peut être libéré.")
        self.status = self.Status.COMPLETED
        self.save(update_fields=["status"])


class Commission(models.Model):
    """Commission prélevée par la plateforme sur une commande, à la libération de l'escrow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="commissions")
    rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Taux en %, ex. 5.00 pour 5%"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "commissions"
        verbose_name = _("commission")
        verbose_name_plural = _("commissions")

    def __str__(self):
        return f"Commission {self.rate}% — {self.amount} (commande {self.order_id})"


class PaymentWebhookEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", _("Reçu")
        PROCESSED = "processed", _("Traité")
        REJECTED = "rejected", _("Rejeté")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        PaymentProvider, on_delete=models.PROTECT, related_name="webhook_events"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="webhook_events",
    )
    external_event_id = models.CharField(max_length=150)
    event_type = models.CharField(max_length=80, blank=True)
    payload_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    error_code = models.CharField(max_length=80, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_webhook_events"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"],
                name="unique_provider_webhook_event",
            )
        ]