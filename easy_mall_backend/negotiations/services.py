from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product, ProductVariant

from .models import Negotiation, NegotiationEvent


def _proposal_kinds():
    return [NegotiationEvent.Kind.PROPOSAL, NegotiationEvent.Kind.COUNTER_PROPOSAL]


def expire_stale_negotiations(now=None):
    now = now or timezone.now()
    stale_ids = list(
        Negotiation.objects.filter(
            Q(status=Negotiation.Status.OPEN, expires_at__lte=now)
            | Q(status=Negotiation.Status.ACCEPTED, reserved_until__lte=now)
        ).values_list("pk", flat=True)
    )
    expired = 0
    for negotiation_id in stale_ids:
        with transaction.atomic():
            negotiation = Negotiation.objects.select_for_update().filter(pk=negotiation_id).first()
            if negotiation is None:
                continue
            is_expired = (
                negotiation.status == Negotiation.Status.OPEN
                and negotiation.expires_at <= now
            ) or (
                negotiation.status == Negotiation.Status.ACCEPTED
                and negotiation.reserved_until is not None
                and negotiation.reserved_until <= now
            )
            if not is_expired:
                continue
            negotiation.status = Negotiation.Status.EXPIRED
            negotiation.save(update_fields=["status", "updated_at"])
            NegotiationEvent.objects.create(
                negotiation=negotiation,
                kind=NegotiationEvent.Kind.EXPIRED,
            )
            expired += 1
    return expired


def expire_if_stale(negotiation, now=None):
    now = now or timezone.now()
    is_expired = (
        negotiation.status == Negotiation.Status.OPEN
        and negotiation.expires_at <= now
    ) or (
        negotiation.status == Negotiation.Status.ACCEPTED
        and negotiation.reserved_until is not None
        and negotiation.reserved_until <= now
    )
    if not is_expired:
        return False
    negotiation.status = Negotiation.Status.EXPIRED
    negotiation.save(update_fields=["status", "updated_at"])
    NegotiationEvent.objects.create(
        negotiation=negotiation,
        kind=NegotiationEvent.Kind.EXPIRED,
    )
    return True


@transaction.atomic
def create_proposal(*, buyer, product_id, variant_id, amount):
    try:
        product = Product.objects.select_for_update().select_related("seller").get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise ValidationError({"product_id": "Annonce introuvable."}) from exc
    if product.seller_id == buyer.pk:
        raise ValidationError({"product_id": "Vous ne pouvez pas négocier votre propre annonce."})
    if (
        product.item_type != Product.ItemType.PRODUCT
        or product.status != Product.Status.PUBLISHED
        or product.moderation_status != Product.ModerationStatus.APPROVED
        or product.is_suspended
        or product.stock_quantity < 1
    ):
        raise ValidationError({"product_id": "Cette annonce n'est pas disponible à la négociation."})
    variant = None
    if product.variants.exists():
        if not variant_id:
            raise ValidationError({"variant_id": "Choisissez une variante avant de négocier."})
        variant = ProductVariant.objects.select_for_update().filter(
            pk=variant_id, product=product
        ).first()
        if variant is None or variant.stock_quantity < 1:
            raise ValidationError({"variant_id": "Cette variante n'est pas disponible."})
    elif variant_id:
        raise ValidationError({"variant_id": "Cette annonce ne possède pas de variante."})

    negotiation = Negotiation.objects.create(
        product=product,
        variant=variant,
        buyer=buyer,
        seller=product.seller,
        expires_at=timezone.now() + timedelta(hours=settings.NEGOTIATION_OFFER_TTL_HOURS),
    )
    NegotiationEvent.objects.create(
        negotiation=negotiation,
        actor=buyer,
        kind=NegotiationEvent.Kind.PROPOSAL,
        amount=amount,
    )
    return negotiation


@transaction.atomic
def transition_negotiation(*, negotiation_id, actor, action, amount=None):
    negotiation_refs = Negotiation.objects.values("product_id", "variant_id").get(
        pk=negotiation_id
    )
    product_id = negotiation_refs["product_id"]
    Product.objects.select_for_update().get(pk=product_id)
    variant_id = negotiation_refs["variant_id"]
    variant = None
    if variant_id:
        variant = ProductVariant.objects.select_for_update().get(
            pk=variant_id, product_id=product_id
        )
    negotiation = Negotiation.objects.select_for_update().select_related(
        "product", "variant", "buyer", "seller"
    ).get(pk=negotiation_id)
    now = timezone.now()
    if expire_if_stale(negotiation, now):
        raise ValidationError({"status": "Cette négociation a expiré."})
    if actor.pk not in {negotiation.buyer_id, negotiation.seller_id}:
        raise ValidationError({"detail": "Vous ne participez pas à cette négociation."})
    if negotiation.status != Negotiation.Status.OPEN:
        raise ValidationError({"status": "Cette négociation n'est plus ouverte."})

    latest_proposal = negotiation.events.filter(kind__in=_proposal_kinds()).order_by(
        "-created_at", "-id"
    ).first()
    if latest_proposal is None:
        raise ValidationError({"status": "Aucune proposition à traiter."})
    if latest_proposal.actor_id == actor.pk:
        raise ValidationError({"status": "Vous devez attendre la réponse de l'autre participant."})

    if action == "counter":
        max_proposals = settings.NEGOTIATION_MAX_PROPOSALS
        proposal_count = negotiation.events.filter(kind__in=_proposal_kinds()).count()
        if proposal_count >= max_proposals:
            raise ValidationError({"amount": "Le nombre maximal de propositions est atteint."})
        NegotiationEvent.objects.create(
            negotiation=negotiation,
            actor=actor,
            kind=NegotiationEvent.Kind.COUNTER_PROPOSAL,
            amount=amount,
        )
        negotiation.expires_at = now + timedelta(hours=settings.NEGOTIATION_OFFER_TTL_HOURS)
        negotiation.save(update_fields=["expires_at", "updated_at"])
        return negotiation

    if action == "reject":
        negotiation.status = Negotiation.Status.REJECTED
        negotiation.save(update_fields=["status", "updated_at"])
        NegotiationEvent.objects.create(
            negotiation=negotiation, actor=actor, kind=NegotiationEvent.Kind.REJECTED
        )
        return negotiation

    if action != "accept":
        raise ValidationError({"detail": "Action de négociation inconnue."})

    product = negotiation.product
    if not product.is_available:
        raise ValidationError({"status": "Cette annonce n'est plus disponible."})
    if negotiation.variant_id:
        reserved_count = Negotiation.objects.filter(
            variant=variant,
            status=Negotiation.Status.ACCEPTED,
            reserved_until__gt=now,
        ).exclude(pk=negotiation.pk).count()
        if variant.stock_quantity - reserved_count < 1:
            raise ValidationError({"status": "Cette variante est déjà réservée."})
    else:
        reserved_count = Negotiation.objects.filter(
            product=product,
            variant__isnull=True,
            status=Negotiation.Status.ACCEPTED,
            reserved_until__gt=now,
        ).exclude(pk=negotiation.pk).count()
        if product.stock_quantity - reserved_count < 1:
            raise ValidationError({"status": "Cet article est déjà réservé."})

    negotiation.status = Negotiation.Status.ACCEPTED
    negotiation.accepted_price = latest_proposal.amount
    negotiation.reserved_until = now + timedelta(
        minutes=settings.NEGOTIATION_RESERVATION_MINUTES
    )
    negotiation.expires_at = negotiation.reserved_until
    negotiation.save(
        update_fields=["status", "accepted_price", "reserved_until", "expires_at", "updated_at"]
    )
    NegotiationEvent.objects.create(
        negotiation=negotiation,
        actor=actor,
        kind=NegotiationEvent.Kind.ACCEPTED,
        amount=latest_proposal.amount,
    )
    return negotiation