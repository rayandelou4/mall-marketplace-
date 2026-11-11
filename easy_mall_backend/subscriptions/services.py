import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment, PaymentProvider, PaymentWebhookEvent
from payments.provider_service import get_payment_adapter

from .models import Subscription, SubscriptionPlan, SubscriptionSettings


class PaymentInitializationUnavailable(APIException):
    status_code = 503
    default_detail = "Aucun adaptateur de paiement actif n'est configuré."
    default_code = "payment_provider_unavailable"


def start_subscription_payment(*, user, plan, provider, idempotency_key, return_url):
    if not user.is_active or user.is_suspended:
        raise ValidationError({"user": "Ce compte ne peut pas souscrire actuellement."})
    if not plan.is_active or plan.is_archived:
        raise ValidationError({"plan": "Ce forfait n'est plus disponible."})
    adapter = get_payment_adapter(provider)
    if adapter is None:
        raise PaymentInitializationUnavailable()

    try:
        with transaction.atomic():
            existing = Payment.objects.select_for_update().filter(
                idempotency_key=idempotency_key
            ).select_related("subscription").first()
            if existing:
                if (
                    existing.subscription_id is None
                    or existing.subscription.user_id != user.pk
                    or existing.subscription.plan_id != plan.pk
                    or existing.provider_id != provider.pk
                ):
                    raise ValidationError({"idempotency_key": "Cette clé a déjà été utilisée."})
                payment = existing
                subscription = existing.subscription
                should_initialize = not existing.external_reference and existing.status == Payment.Status.PENDING
            else:
                subscription = Subscription.objects.create(
                    user=user,
                    plan=plan,
                    amount_paid=plan.amount,
                    currency=plan.currency,
                    duration_days=plan.duration_days,
                    status=Subscription.Status.PENDING,
                )
                payment = Payment.objects.create(
                    subscription=subscription,
                    provider=provider,
                    amount=plan.amount,
                    currency=plan.currency,
                    status=Payment.Status.PENDING,
                    transaction_reference=str(uuid.uuid4()),
                    idempotency_key=idempotency_key,
                )
                should_initialize = True
    except IntegrityError as exc:
        raise ValidationError({"idempotency_key": "La requête de paiement existe déjà."}) from exc

    if not should_initialize:
        return subscription, payment, {}

    try:
        result = adapter.initialize_payment(payment=payment, return_url=return_url)
        if not isinstance(result, dict) or not result.get("external_reference"):
            raise ValueError("L'adaptateur doit retourner une référence externe.")
        payment.external_reference = str(result["external_reference"])[:150]
        payment.save(update_fields=["external_reference"])
        return subscription, payment, {
            key: result[key]
            for key in ("redirect_url", "instructions", "expires_at")
            if key in result
        }
    except Exception as exc:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
            if payment.status == Payment.Status.PENDING:
                payment.status = Payment.Status.FAILED
                payment.metadata = {"initialization_error": type(exc).__name__}
                payment.save(update_fields=["status", "metadata"])
                subscription.status = Subscription.Status.PAST_DUE
                subscription.save(update_fields=["status", "updated_at"])
        raise PaymentInitializationUnavailable() from exc


def _reject_webhook(provider, raw_body, code, event_id=None, event_type=""):
    digest = hashlib.sha256(raw_body).hexdigest()
    identifier = (event_id or f"invalid-{digest}")[:150]
    PaymentWebhookEvent.objects.get_or_create(
        provider=provider,
        external_event_id=identifier,
        defaults={
            "event_type": event_type[:80],
            "payload_sha256": digest,
            "status": PaymentWebhookEvent.Status.REJECTED,
            "error_code": code[:80],
            "processed_at": timezone.now(),
        },
    )
    raise ValidationError({"detail": "La notification de paiement n'a pas pu être vérifiée."})


def process_subscription_webhook(*, provider, raw_body, headers):
    adapter = get_payment_adapter(provider)
    if adapter is None:
        raise PaymentInitializationUnavailable()
    if not adapter.verify_webhook(raw_body=raw_body, headers=headers):
        _reject_webhook(provider, raw_body, "invalid_signature")

    try:
        event = adapter.parse_webhook(raw_body=raw_body, headers=headers)
        event_id = str(event["event_id"])
        external_reference = str(event["external_reference"])
        transaction_reference = str(event["transaction_reference"])
        event_type = str(event.get("event_type", ""))[:80]
    except (KeyError, TypeError, ValueError) as exc:
        _reject_webhook(provider, raw_body, "invalid_payload")
        raise exc

    digest = hashlib.sha256(raw_body).hexdigest()
    try:
        webhook_event, created = PaymentWebhookEvent.objects.get_or_create(
            provider=provider,
            external_event_id=event_id[:150],
            defaults={
                "event_type": event_type,
                "payload_sha256": digest,
            },
        )
    except IntegrityError:
        webhook_event = PaymentWebhookEvent.objects.get(
            provider=provider, external_event_id=event_id[:150]
        )
        created = False
    if not created:
        return webhook_event, False

    payment = Payment.objects.filter(
        provider=provider,
        external_reference=external_reference,
        transaction_reference=transaction_reference,
        subscription__isnull=False,
    ).select_related("subscription", "subscription__user", "subscription__plan").first()
    if payment is None:
        webhook_event.status = PaymentWebhookEvent.Status.REJECTED
        webhook_event.error_code = "payment_not_found"
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=["status", "error_code", "processed_at"])
        raise ValidationError({"detail": "Transaction de souscription introuvable."})

    try:
        verified = adapter.verify_transaction(external_reference=external_reference)
        if not isinstance(verified, dict):
            raise ValueError("invalid_verification")
        verified_amount = Decimal(str(verified["amount"]))
        verified_currency = str(verified["currency"]).upper()
        is_successful = verified.get("status") == "successful"
        is_matching = (
            str(verified.get("external_reference")) == payment.external_reference
            and str(verified.get("transaction_reference")) == payment.transaction_reference
            and verified_amount == payment.amount
            and verified_currency == payment.currency
        )
    except (KeyError, TypeError, ValueError, ArithmeticError):
        is_successful = False
        is_matching = False

    with transaction.atomic():
        webhook_event = PaymentWebhookEvent.objects.select_for_update().get(pk=webhook_event.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        subscription = Subscription.objects.select_for_update().get(pk=payment.subscription_id)
        if webhook_event.status == PaymentWebhookEvent.Status.PROCESSED:
            return webhook_event, False
        if not is_matching:
            webhook_event.status = PaymentWebhookEvent.Status.REJECTED
            webhook_event.error_code = "transaction_mismatch"
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["status", "error_code", "processed_at"])
            raise ValidationError({"detail": "Montant, devise ou référence non correspondants."})
        if payment.status != Payment.Status.PENDING or subscription.status != Subscription.Status.PENDING:
            webhook_event.status = PaymentWebhookEvent.Status.REJECTED
            webhook_event.error_code = "invalid_transition"
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["status", "error_code", "processed_at"])
            return webhook_event, False

        if is_successful:
            now = timezone.now()
            starts_at = now
            if subscription.previous_subscription_id:
                previous = Subscription.objects.select_for_update().get(
                    pk=subscription.previous_subscription_id
                )
                policy = SubscriptionSettings.objects.get_or_create(pk=1)[0].plan_change_policy
                if policy == SubscriptionSettings.PlanChangePolicy.AT_PERIOD_END and previous.expires_at and previous.expires_at > now:
                    starts_at = previous.expires_at
                else:
                    previous.status = Subscription.Status.CANCELLED
                    previous.auto_renew = False
                    previous.cancelled_at = now
                    previous.save(update_fields=["status", "auto_renew", "cancelled_at", "updated_at"])

            payment.status = Payment.Status.SUCCESSFUL
            payment.confirmed_at = now
            payment.save(update_fields=["status", "confirmed_at"])
            subscription.status = Subscription.Status.ACTIVE
            subscription.starts_at = starts_at
            subscription.expires_at = starts_at + timedelta(days=subscription.duration_days)
            subscription.next_payment_at = None
            subscription.save(update_fields=[
                "status", "starts_at", "expires_at", "next_payment_at", "updated_at"
            ])
                notify(
                    subscription.user,
                    Notification.NotificationType.SUBSCRIPTION_CONFIRMED,
                    "Abonnement confirmé",
                    f"Votre abonnement {subscription.plan.name} est activé.",
                    "/mon-abonnement",
                )
        else:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            subscription.status = Subscription.Status.PAST_DUE
            subscription.save(update_fields=["status", "updated_at"])
            notify(
                subscription.user,
                Notification.NotificationType.SUBSCRIPTION_PAYMENT_FAILED,
                "Paiement d’abonnement échoué",
                f"Le paiement du forfait {subscription.plan.name} n’a pas été confirmé.",
                "/abonnements",
            )

        webhook_event.payment = payment
        webhook_event.status = PaymentWebhookEvent.Status.PROCESSED
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=["payment", "status", "processed_at"])
    return webhook_event, True