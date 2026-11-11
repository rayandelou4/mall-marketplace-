from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .alerting import (
    notify_price_drop,
    notify_saved_search_matches,
    reset_price_alerts_above_target,
)
from .models import Product


def _is_publicly_available(product):
    return bool(
        product.is_available
        and product.seller.is_active
        and not product.seller.is_suspended
    )


@receiver(pre_save, sender=Product)
def remember_product_alert_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._alert_previous_state = None
        return
    previous = sender.objects.select_related("seller").filter(pk=instance.pk).first()
    instance._alert_previous_state = (
        {
            "available": _is_publicly_available(previous),
            "price": previous.price,
        }
        if previous
        else None
    )


@receiver(post_save, sender=Product)
def send_product_alerts(sender, instance, created, **kwargs):
    previous = getattr(instance, "_alert_previous_state", None)
    available = _is_publicly_available(instance)
    if not available:
        return

    product_id = instance.pk
    if previous is None or not previous["available"]:
        transaction.on_commit(
            lambda: notify_saved_search_matches(product_id), robust=True
        )
        return

    previous_price = previous["price"]
    current_price = instance.price
    if current_price < previous_price:
        transaction.on_commit(
            lambda: notify_price_drop(product_id, previous_price, current_price),
            robust=True,
        )
    elif current_price > previous_price:
        transaction.on_commit(
            lambda: reset_price_alerts_above_target(product_id, current_price),
            robust=True,
        )