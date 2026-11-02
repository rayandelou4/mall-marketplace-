"""
Déblocage des fonds retenus en escrow (§8 du document d'architecture).

Déclenché par la confirmation de réception de l'acheteur (`Order.confirm_receipt`,
app `orders`). Une tâche planifiée pourrait plus tard appeler la même fonction
pour les commandes dont `escrow_release_at` est dépassé sans action de l'acheteur.
"""

from decimal import Decimal

from django.db import transaction

from orders.models import Order

from .models import Commission, Payment, Wallet

COMMISSION_RATE = Decimal("5.00")  # % — fixe pour l'instant, configurable par marché/catégorie plus tard


@transaction.atomic
def release_order_payment(order):
    """
    Débloque tous les paiements en escrow d'une commande : crédite chaque
    vendeur impliqué (net de commission), enregistre la commission prélevée,
    et clôt la commande.
    """
    payments = order.payments.filter(status=Payment.Status.HELD_ESCROW)
    if not payments.exists():
        raise ValueError("Aucun paiement en attente de déblocage pour cette commande.")

    for item in order.items.select_related("seller", "product"):
        seller_amount = item.subtotal
        commission_amount = (seller_amount * COMMISSION_RATE / Decimal("100")).quantize(Decimal("0.01"))
        net_amount = seller_amount - commission_amount

        wallet, _ = Wallet.objects.get_or_create(user=item.seller, defaults={"currency": order.currency})
        wallet.credit(net_amount)

        Commission.objects.create(order=order, rate=COMMISSION_RATE, amount=commission_amount)

    payments.update(status=Payment.Status.COMPLETED)

    order.status = Order.Status.DELIVERED
    order.save(update_fields=["status"])
