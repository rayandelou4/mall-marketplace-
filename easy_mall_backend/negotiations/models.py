import uuid

from django.conf import settings
from django.db import models


class Negotiation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "En cours"
        ACCEPTED = "accepted", "Acceptée, à commander"
        REJECTED = "rejected", "Refusée"
        EXPIRED = "expired", "Expirée"
        COMPLETED = "completed", "Commandée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="negotiations"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiations",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="price_negotiations_as_buyer",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="price_negotiations_as_seller",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    accepted_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expires_at = models.DateTimeField()
    reserved_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "price_negotiations"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]


class NegotiationEvent(models.Model):
    class Kind(models.TextChoices):
        PROPOSAL = "proposal", "Proposition"
        COUNTER_PROPOSAL = "counter_proposal", "Contre-proposition"
        ACCEPTED = "accepted", "Acceptation"
        REJECTED = "rejected", "Refus"
        EXPIRED = "expired", "Expiration"
        CHECKOUT = "checkout", "Commande créée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    negotiation = models.ForeignKey(
        Negotiation, on_delete=models.CASCADE, related_name="events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negotiation_events",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "negotiation_events"
        ordering = ["created_at", "id"]