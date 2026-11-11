from django.db.models import Q

from notifications.models import NotificationPreference
from notifications.services import notify

from .models import Favorite, Product, SavedSearch


def _is_publicly_available(product):
    return bool(
        product
        and product.is_available
        and product.seller.is_active
        and not product.seller.is_suspended
    )


def _matches_saved_search(product, saved_search):
    params = saved_search.query_params
    if not isinstance(params, dict):
        return False
    from .views import ProductFilter

    queryset = Product.objects.filter(pk=product.pk)
    product_filter = ProductFilter(data=params, queryset=queryset)
    if not product_filter.is_valid() or not product_filter.qs.exists():
        return False
    search = " ".join(str(params.get("search", "")).split())
    for word in search.split():
        if not queryset.filter(
            Q(title__icontains=word)
            | Q(description__icontains=word)
            | Q(category__name__icontains=word)
        ).exists():
            return False
    return True


def notify_saved_search_matches(product_id):
    product = Product.objects.select_related("seller", "category").filter(pk=product_id).first()
    if not _is_publicly_available(product):
        return 0
    notified_users = set()
    for saved_search in SavedSearch.objects.exclude(user_id=product.seller_id).select_related("user"):
        if saved_search.user_id in notified_users or not _matches_saved_search(product, saved_search):
            continue
        notified_users.add(saved_search.user_id)
        notify(
            saved_search.user,
            "saved_search_match",
            "Nouvelle annonce correspondant à votre recherche",
            f"{product.title} · {product.price} {product.currency}",
            f"/produit/{product.pk}",
        )
    return len(notified_users)


def notify_price_drop(product_id, previous_price, new_price):
    product = Product.objects.select_related("seller").filter(pk=product_id).first()
    if (
        new_price >= previous_price
        or not _is_publicly_available(product)
    ):
        return 0

    notified = 0
    favorites = Favorite.objects.filter(
        product=product,
        target_price__gte=new_price,
    ).exclude(user_id=product.seller_id).select_related("user")
    for favorite in favorites:
        if (
            favorite.last_notified_price is not None
            and new_price >= favorite.last_notified_price
        ):
            continue
        notification = notify(
            favorite.user,
            "price_drop",
            "Le prix d’un produit suivi a baissé",
            f"{product.title} est maintenant à {product.price} {product.currency}.",
            f"/produit/{product.pk}",
        )
        if notification is None:
            continue
        Favorite.objects.filter(pk=favorite.pk).update(last_notified_price=new_price)
        notified += 1
    return notified


def reset_price_alerts_above_target(product_id, new_price):
    return Favorite.objects.filter(
        product_id=product_id,
        target_price__lt=new_price,
    ).update(last_notified_price=None)