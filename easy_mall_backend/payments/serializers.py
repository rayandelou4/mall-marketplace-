"""
Serializers de l'app `payments`.
"""

import uuid

from django.db import transaction
from rest_framework import serializers

from orders.models import Order

from .models import PaymentProvider, SupportedMarket, Payment, Wallet


class SupportedMarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportedMarket
        fields = ["id", "country_code", "country_name", "currency_code"]


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["id", "balance", "currency", "updated_at"]
        read_only_fields = fields


class PaymentProviderSerializer(serializers.ModelSerializer):
    market = SupportedMarketSerializer(read_only=True)

    class Meta:
        model = PaymentProvider
        fields = ["id", "code", "provider_type", "market", "is_active"]


class PaymentSerializer(serializers.ModelSerializer):
    """Lecture — suivi de l'état d'un paiement (acheteur/vendeur)."""

    provider = PaymentProviderSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "order", "provider", "amount", "currency", "status",
            "transaction_reference", "created_at", "confirmed_at", "escrow_release_at",
        ]
        read_only_fields = fields


class PaymentInitiateSerializer(serializers.Serializer):
    """
    Démarre un paiement pour une commande : crée l'enregistrement `Payment`
    en statut `pending`. L'appel réel à l'API du fournisseur (webhook,
    redirection USSD pour Mobile Money...) se fait ensuite côté vue, via
    l'adaptateur correspondant (pattern décrit au §8 de l'architecture).
    """

    order_id = serializers.UUIDField()
    provider_id = serializers.UUIDField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(pk=value, buyer=self.context["request"].user)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError("Cette commande n'est plus en attente de paiement.")
        if order.payment_method != Order.PaymentMethod.MOBILE_MONEY:
            raise serializers.ValidationError(
                "Une commande payée en espèces ne peut pas démarrer un paiement Mobile Money."
            )
        self.order = order
        return value

    def validate_provider_id(self, value):
        try:
            provider = PaymentProvider.objects.get(pk=value, is_active=True)
        except PaymentProvider.DoesNotExist:
            raise serializers.ValidationError("Moyen de paiement indisponible.")
        self.provider = provider
        return value

    @transaction.atomic
    def save(self):
        order = Order.objects.select_for_update().get(pk=self.order.pk)
        if order.status != Order.Status.PENDING:
            raise serializers.ValidationError("Cette commande n'est plus en attente de paiement.")

        existing_payment = Payment.objects.select_for_update().filter(
            order=order,
            status=Payment.Status.PENDING,
        ).first()
        if existing_payment:
            if existing_payment.provider_id != self.provider.pk:
                raise serializers.ValidationError(
                    "Un paiement est déjà en cours pour cette commande."
                )
            return existing_payment

        return Payment.objects.create(
            order=order,
            provider=self.provider,
            amount=order.total_amount,
            currency=order.currency,
            transaction_reference=str(uuid.uuid4()),
        )


class PaymentConfirmSerializer(serializers.Serializer):
    """
    Confirmation d'un paiement — appelée par le webhook du fournisseur
    (pas directement par l'acheteur). Place les fonds en escrow (§8).
    """

    transaction_reference = serializers.CharField()

    def validate_transaction_reference(self, value):
        try:
            payment = Payment.objects.select_related("order").get(transaction_reference=value)
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Paiement introuvable.")
        if payment.status != Payment.Status.PENDING:
            raise serializers.ValidationError("Ce paiement a déjà été traité.")
        self.payment = payment
        return value

    @transaction.atomic
    def save(self):
        order = Order.objects.select_for_update().get(pk=self.payment.order_id)
        payment = Payment.objects.select_for_update().get(pk=self.payment.pk)
        if payment.status != Payment.Status.PENDING or order.status != Order.Status.PENDING:
            raise serializers.ValidationError("Ce paiement a déjà été traité ou la commande a changé d'état.")
        payment.mark_held_escrow()
        order.status = Order.Status.PAID
        order.save(update_fields=["status"])
        return payment
