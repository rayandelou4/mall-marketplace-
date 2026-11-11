from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.utils import timezone

from .models import LoyaltyProgram, LoyaltyTransaction, Promotion

CENT = Decimal("0.01")


def get_loyalty_program():
    return LoyaltyProgram.objects.get_or_create(pk=1)[0]


def get_points_balance(user):
    return LoyaltyTransaction.objects.filter(user=user).aggregate(
        balance=Sum("points_delta")
    )["balance"] or 0


def get_currency_rule(program, currency, key, fallback):
    try:
        value = Decimal(str(program.currency_rules.get(currency, {}).get(key, fallback)))
        return value if value.is_finite() and value >= 0 else fallback
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return fallback


def calculate_checkout_quote(entries, buyer, points_requested=0):
    """Calcule les meilleures offres et la fidélité depuis les données serveur."""
    now = timezone.now()
    product_ids = {entry["product"].pk for entry in entries}
    promotions = list(
        Promotion.objects.filter(
            is_active=True,
            products__in=product_ids,
        )
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .select_related("seller")
        .prefetch_related("products")
        .distinct()
    )
    quantities_by_product = {}
    for entry in entries:
        product_id = entry["product"].pk
        quantities_by_product[product_id] = quantities_by_product.get(product_id, 0) + entry["quantity"]

    prepared = []
    for entry in entries:
        product = entry["product"]
        quantity = entry["quantity"]
        shipping = (
            product.shipping_cost
            if product.sale_method == product.SaleMethod.DELIVERY
            else Decimal("0.00")
        )
        original_shipping = shipping
        candidates = []
        negotiated_unit_price = entry.get("negotiated_unit_price")
        for promotion in (() if negotiated_unit_price is not None else promotions):
            covered_ids = {item.pk for item in promotion.products.all()}
            if (
                product.pk not in covered_ids
                or promotion.seller_id != product.seller_id
                or promotion.min_customer_purchases > buyer.total_purchases
                or sum(quantities_by_product.get(item_id, 0) for item_id in covered_ids)
                < promotion.min_quantity
                or (promotion.currency and promotion.currency != product.currency)
            ):
                continue

            unit_price = product.price
            if promotion.discount_type == Promotion.DiscountType.PERCENTAGE:
                discount_per_unit = (
                    product.price * promotion.value / Decimal("100")
                ).quantize(CENT, rounding=ROUND_HALF_UP)
                unit_price = max(Decimal("0.00"), product.price - discount_per_unit)
            elif promotion.discount_type == Promotion.DiscountType.FIXED:
                unit_price = max(Decimal("0.00"), product.price - promotion.value)
            elif promotion.value < product.price:
                unit_price = promotion.value

            discounted_shipping = Decimal("0.00") if promotion.free_shipping else shipping
            saving = (product.price - unit_price) * quantity + shipping - discounted_shipping
            if saving > 0:
                candidates.append((saving, promotion, unit_price, discounted_shipping))

        if negotiated_unit_price is not None:
            unit_price = negotiated_unit_price
            promotion_name = "Prix négocié"
        elif candidates:
            _saving, chosen, unit_price, shipping = max(
                candidates, key=lambda candidate: (candidate[0], candidate[1].created_at)
            )
            promotion_name = chosen.name
        else:
            unit_price = product.price
            promotion_name = ""

        prepared.append({
            **entry,
            "original_unit_price": product.price,
            "unit_price": unit_price,
            "promotion_discount": (
                (product.price - unit_price) * quantity
                if negotiated_unit_price is None
                else Decimal("0.00")
            ),
            "promotion_name": promotion_name,
            "shipping_cost": shipping,
            "original_shipping_cost": original_shipping,
            "loyalty_discount": Decimal("0.00"),
        })

    base_total = sum(
        (row["unit_price"] * row["quantity"] + row["shipping_cost"] for row in prepared),
        Decimal("0.00"),
    )
    program = get_loyalty_program()
    balance = get_points_balance(buyer)
    currency = entries[0]["product"].currency if entries else ""
    redemption_value = get_currency_rule(
        program, currency, "redemption_value_per_point", program.redemption_value_per_point
    )
    points_requested = max(0, int(points_requested or 0))
    points_redeemed = 0
    loyalty_discount = Decimal("0.00")
    if program.is_active and points_requested and redemption_value > 0:
        points_requested = min(points_requested, balance)
        maximum_discount = (
            base_total * program.max_redemption_percent / Decimal("100")
        ).quantize(CENT, rounding=ROUND_DOWN)
        loyalty_discount = min(
            (redemption_value * points_requested).quantize(
                CENT, rounding=ROUND_DOWN
            ),
            maximum_discount,
            base_total,
        )
        points_redeemed = min(
            points_requested,
            int((loyalty_discount / redemption_value).to_integral_value(rounding=ROUND_DOWN)),
        )
        loyalty_discount = (
            redemption_value * points_redeemed
        ).quantize(CENT, rounding=ROUND_DOWN)

    remaining_discount = loyalty_discount
    remaining_base = base_total
    for index, row in enumerate(prepared):
        line_base = row["unit_price"] * row["quantity"] + row["shipping_cost"]
        if index == len(prepared) - 1:
            allocation = remaining_discount
        elif remaining_base:
            allocation = (remaining_discount * line_base / remaining_base).quantize(
                CENT, rounding=ROUND_DOWN
            )
        else:
            allocation = Decimal("0.00")
        row["loyalty_discount"] = min(allocation, line_base)
        remaining_discount -= row["loyalty_discount"]
        remaining_base -= line_base

    remaining_points = points_redeemed
    for index, row in enumerate(prepared):
        if index == len(prepared) - 1:
            allocation = remaining_points
        elif loyalty_discount:
            allocation = int(
                (Decimal(points_redeemed) * row["loyalty_discount"] / loyalty_discount)
                .to_integral_value(rounding=ROUND_DOWN)
            )
        else:
            allocation = 0
        row["loyalty_points_redeemed"] = allocation
        remaining_points -= allocation

    return {
        "items": prepared,
        "currency": entries[0]["product"].currency if entries else "",
        "points_balance": balance,
        "points_redeemed": points_redeemed,
        "loyalty_discount": loyalty_discount,
        "total_before_loyalty": base_total,
        "total": base_total - loyalty_discount,
    }


def award_order_points(order):
    if order.status != order.Status.DELIVERED:
        return 0
    program = get_loyalty_program()
    points_rate = get_currency_rule(
        program,
        order.currency,
        "points_per_currency_unit",
        program.points_per_currency_unit,
    )
    if not program.is_active or points_rate <= 0:
        return 0
    points = int(
        (order.total_amount * points_rate).to_integral_value(
            rounding=ROUND_DOWN
        )
    )
    if points <= 0:
        return 0
    transaction, created = LoyaltyTransaction.objects.get_or_create(
        user=order.buyer,
        order=order,
        kind=LoyaltyTransaction.Kind.EARNED,
        defaults={
            "checkout_group": order.checkout_group,
            "points_delta": points,
        },
    )
    return transaction.points_delta if created else 0