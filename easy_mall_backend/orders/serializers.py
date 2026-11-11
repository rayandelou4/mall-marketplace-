"""
Serializers de l'app `orders`.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from catalog.models import Product, ProductVariant, StockMovement
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment
from localization.models import PrivateAddress
from promotions.models import LoyaltyTransaction
from promotions.services import calculate_checkout_quote
from negotiations.models import Negotiation, NegotiationEvent
from negotiations.services import expire_if_stale

from .models import CheckoutGroup, Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    subtotal = serializers.ReadOnlyField()
    # La devise vit sur la commande parente, pas sur la ligne elle-même.
    currency = serializers.CharField(source="order.currency", read_only=True)
    payment_method = serializers.CharField(
        source="order.payment_method", read_only=True
    )
    order_status = serializers.CharField(source="order.status", read_only=True)
    order_created_at = serializers.DateTimeField(
        source="order.created_at", read_only=True
    )
    shipping_address = serializers.CharField(
        source="order.shipping_address", read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "order_status",
            "order_created_at",
            "shipping_address",
            "product",
            "variant",
            "negotiation",
            "variant_label",
            "product_title",
            "seller_username",
            "quantity",
            "unit_price",
            "original_unit_price",
            "promotion_discount",
            "promotion_name",
            "loyalty_discount",
            "loyalty_points_redeemed",
            "shipping_cost",
            "original_shipping_cost",
            "sale_method",
            "subtotal",
            "currency",
            "payment_method",
            "is_shipped",
        ]


class OrderListSerializer(serializers.ModelSerializer):
    """Version allégée pour l'historique des commandes."""

    items_count = serializers.ReadOnlyField()
    sellers = serializers.SerializerMethodField()
    has_delivery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "payment_method",
            "total_amount",
            "currency",
            "items_count",
            "sellers",
            "has_delivery",
            "created_at",
        ]

    def get_sellers(self, obj):
        return list(obj.items.values_list("seller__username", flat=True).distinct())

    def get_has_delivery(self, obj):
        return any(item.sale_method == "delivery" for item in obj.items.all())


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "payment_method",
            "total_amount",
            "loyalty_points_redeemed",
            "loyalty_discount_amount",
            "currency",
            "shipping_address",
            "items",
            "created_at",
            "updated_at",
        ]


class CheckoutGroupDetailSerializer(serializers.ModelSerializer):
    orders = OrderDetailSerializer(many=True, read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = CheckoutGroup
        fields = [
            "id", "currency", "total_amount", "loyalty_points_redeemed",
            "loyalty_discount_amount", "orders", "items", "created_at",
        ]

    def get_items(self, obj):
        items = OrderItem.objects.filter(order__checkout_group=obj).select_related(
            "order", "seller", "product"
        )
        return OrderItemSerializer(items, many=True, context=self.context).data


class OrderCreateSerializer(serializers.Serializer):
    """
    Création d'une commande à partir du panier (checkout).
    Chaque ligne fige le titre/prix du produit au moment de l'achat — voir
    `OrderItem.product_title` / `unit_price` dans le modèle.
    """

    shipping_address = serializers.CharField(required=False, allow_blank=False)
    private_address_id = serializers.UUIDField(required=False, write_only=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    points_to_redeem = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        if self.context.get("quote_only"):
            return attrs
        address_id = attrs.pop("private_address_id", None)
        requires_delivery = any(
            entry["product"].sale_method == Product.SaleMethod.DELIVERY
            for entry in attrs["items"]
        )
        if address_id:
            buyer = self.context["request"].user
            address = (
                PrivateAddress.objects.filter(pk=address_id, user=buyer)
                .select_related("country", "administrative_area", "locality")
                .first()
            )
            if address is None:
                raise serializers.ValidationError(
                    {"private_address_id": "Adresse introuvable ou non autorisée."}
                )
            if requires_delivery:
                parts = [
                    address.country.name,
                    address.administrative_area.name if address.administrative_area else "",
                    address.locality.name if address.locality else "",
                    address.street_address,
                    address.landmark,
                ]
                attrs["shipping_address"] = ", ".join(part for part in parts if part)
                attrs["shipping_address_record"] = address
        elif requires_delivery and not attrs.get("shipping_address", "").strip():
            raise serializers.ValidationError(
                {
                    "shipping_address": "Choisissez une adresse enregistrée ou indiquez une adresse de livraison."
                }
            )
        else:
            attrs["shipping_address"] = ""
        return attrs

    def get_quote(self):
        quote = calculate_checkout_quote(
            self.validated_data["items"],
            self.context["request"].user,
            self.validated_data.get("points_to_redeem", 0),
        )
        return {
            "currency": quote["currency"],
            "points_balance": quote["points_balance"],
            "points_redeemed": quote["points_redeemed"],
            "loyalty_discount": quote["loyalty_discount"],
            "total_before_loyalty": quote["total_before_loyalty"],
            "total": quote["total"],
            "items": [
                {
                    "product_id": str(item["product"].pk),
                    "variant_id": str(item["variant"].pk) if item["variant"] else None,
                    "negotiation_id": str(item["negotiation"].pk) if item.get("negotiation") else None,
                    "product_title": item["product"].title,
                    "quantity": item["quantity"],
                    "original_unit_price": item["original_unit_price"],
                    "unit_price": item["unit_price"],
                    "promotion_discount": item["promotion_discount"],
                    "promotion_name": item["promotion_name"],
                    "original_shipping_cost": item["original_shipping_cost"],
                    "shipping_cost": item["shipping_cost"],
                    "loyalty_discount": item["loyalty_discount"],
                }
                for item in quote["items"]
            ],
        }

    def validate_items(self, value):
        requested_quantities = {}
        expected_prices = {}
        conversion_visitors = {}
        variant_ids = {}
        negotiation_ids = {}
        for entry in value:
            try:
                product_id = uuid.UUID(str(entry["product_id"]))
                variant_id = uuid.UUID(str(entry["variant_id"])) if entry.get("variant_id") else None
                negotiation_id = uuid.UUID(str(entry["negotiation_id"])) if entry.get("negotiation_id") else None
                raw_quantity = entry.get("quantity", 1)
                if isinstance(raw_quantity, bool):
                    raise ValueError
                quantity = int(raw_quantity)
                if isinstance(raw_quantity, float) and not raw_quantity.is_integer():
                    raise ValueError
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise serializers.ValidationError(
                    "Chaque item doit contenir 'product_id' et 'quantity'."
                ) from exc
            if quantity < 1:
                raise serializers.ValidationError("La quantité doit être au moins 1.")
            line_key = (product_id, variant_id)
            requested_quantities[line_key] = (
                requested_quantities.get(line_key, 0) + quantity
            )
            try:
                expected_unit_price = (
                    Decimal(str(entry["unit_price"])) if "unit_price" in entry else None
                )
                expected_shipping_cost = (
                    Decimal(str(entry["shipping_cost"]))
                    if "shipping_cost" in entry
                    else None
                )
                if (
                    expected_unit_price is not None
                    and not expected_unit_price.is_finite()
                ) or (
                    expected_shipping_cost is not None
                    and not expected_shipping_cost.is_finite()
                ):
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    "Le prix ou les frais de livraison transmis sont invalides."
                ) from exc
            expected = (expected_unit_price, expected_shipping_cost)
            if (
                line_key in expected_prices
                and expected_prices[line_key] != expected
            ):
                raise serializers.ValidationError(
                    "Les informations de prix sont incohérentes pour un même article."
                )
            expected_prices[line_key] = expected
            try:
                conversion_visitor_id = (
                    uuid.UUID(str(entry["conversion_visitor_id"]))
                    if entry.get("conversion_visitor_id")
                    else None
                )
            except (TypeError, ValueError, AttributeError) as exc:
                raise serializers.ValidationError(
                    "L’identifiant de session de conversion est invalide."
                ) from exc
            if (
                line_key in conversion_visitors
                and conversion_visitors[line_key] != conversion_visitor_id
            ):
                raise serializers.ValidationError(
                    "Les identifiants de session sont incohérents pour un même article."
                )
            conversion_visitors[line_key] = conversion_visitor_id
            variant_ids[line_key] = variant_id
            if line_key in negotiation_ids and negotiation_ids[line_key] != negotiation_id:
                raise serializers.ValidationError(
                    "Une même ligne ne peut pas mélanger prix négocié et prix catalogue."
                )
            negotiation_ids[line_key] = negotiation_id

        requested_product_ids = {product_id for product_id, _variant_id in requested_quantities}
        products = {
            product.pk: product
            for product in Product.objects.select_related("seller").filter(
                pk__in=requested_product_ids
            )
        }
        missing_ids = requested_product_ids - products.keys()
        if missing_ids:
            raise serializers.ValidationError(
                f"Produit {next(iter(missing_ids))} introuvable."
            )
        currencies = {product.currency for product in products.values()}
        if len(currencies) > 1:
            raise serializers.ValidationError(
                "Tous les articles d'une commande doivent utiliser la même devise."
            )

        cleaned = []
        variants = {
            variant.pk: variant
            for variant in ProductVariant.objects.filter(
                pk__in=[variant_id for variant_id in variant_ids.values() if variant_id]
            )
        }
        negotiations = {
            negotiation.pk: negotiation
            for negotiation in Negotiation.objects.filter(
                pk__in=[negotiation_id for negotiation_id in negotiation_ids.values() if negotiation_id]
            ).select_related("product", "variant")
        }
        for line_key, quantity in requested_quantities.items():
            product_id, variant_id = line_key
            product = products[product_id]
            variant = variants.get(variant_id)
            negotiation_id = negotiation_ids.get(line_key)
            negotiation = negotiations.get(negotiation_id)
            if negotiation_id and negotiation is None:
                raise serializers.ValidationError("La négociation est introuvable.")
            if negotiation:
                expire_if_stale(negotiation)
                if (
                    negotiation.status != Negotiation.Status.ACCEPTED
                    or negotiation.buyer_id != self.context["request"].user.pk
                    or negotiation.product_id != product.pk
                    or negotiation.variant_id != (variant.pk if variant else None)
                    or negotiation.reserved_until is None
                    or negotiation.reserved_until <= timezone.now()
                ):
                    raise serializers.ValidationError(
                        "Cette offre n'est pas acceptée, ne vous appartient pas ou sa réservation a expiré."
                    )
                if quantity != 1:
                    raise serializers.ValidationError(
                        "Une négociation acceptée réserve une unité par commande."
                    )
            if product.variants.exists() and variant is None:
                raise serializers.ValidationError(
                    f"Choisissez une variante pour « {product.title} »."
                )
            if variant and variant.product_id != product.pk:
                raise serializers.ValidationError("Cette variante n'appartient pas à cet article.")
            expected_unit_price, expected_shipping_cost = expected_prices[line_key]
            if (
                expected_unit_price is not None
                and expected_unit_price != (
                    negotiation.accepted_price if negotiation else product.price
                )
            ) or (
                expected_shipping_cost is not None
                and expected_shipping_cost != product.shipping_cost
            ):
                raise serializers.ValidationError(
                    f"Le prix ou les frais de livraison de « {product.title} » ont changé. "
                    "Actualisez votre panier avant de commander."
                )
            if product.status == Product.Status.ARCHIVED:
                raise serializers.ValidationError(
                    f"« {product.title} » est archivé et ne peut plus être acheté."
                )
            if not product.is_available:
                raise serializers.ValidationError(
                    f"« {product.title} » n'est plus disponible."
                )
            available_stock = variant.stock_quantity if variant else product.stock_quantity
            reserved_offers = Negotiation.objects.filter(
                status=Negotiation.Status.ACCEPTED,
                reserved_until__gt=timezone.now(),
                product=product,
                variant=variant if variant else None,
            )
            if negotiation:
                reserved_offers = reserved_offers.exclude(pk=negotiation.pk)
            available_stock -= reserved_offers.count()
            if available_stock < quantity:
                raise serializers.ValidationError(
                    f"Stock insuffisant pour « {product.title} » "
                    f"({available_stock} disponible(s))."
                )

            cleaned.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "expected_unit_price": expected_unit_price,
                    "expected_shipping_cost": expected_shipping_cost,
                    "conversion_visitor_id": conversion_visitors.get(line_key),
                    "variant": variant,
                    "negotiation": negotiation,
                    "negotiated_unit_price": negotiation.accepted_price if negotiation else None,
                }
            )
        return cleaned

    @transaction.atomic
    def save(self):
        buyer = self.context["request"].user
        buyer = type(buyer).objects.select_for_update().get(pk=buyer.pk)
        requested_items = self.validated_data["items"]
        requested_quantities = {
            (entry["product"].pk, entry["variant"].pk if entry["variant"] else None): entry["quantity"]
            for entry in requested_items
        }
        conversion_visitors = {
            (entry["product"].pk, entry["variant"].pk if entry["variant"] else None): entry["conversion_visitor_id"]
            for entry in requested_items
        }
        expected_prices = {
            (entry["product"].pk, entry["variant"].pk if entry["variant"] else None): (
                entry["expected_unit_price"],
                entry["expected_shipping_cost"],
            )
            for entry in requested_items
        }
        negotiation_ids = {
            (entry["product"].pk, entry["variant"].pk if entry["variant"] else None): (
                entry["negotiation"].pk if entry.get("negotiation") else None
            )
            for entry in requested_items
        }
        locked_products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .select_related("seller")
            .filter(pk__in={product_id for product_id, _variant_id in requested_quantities})
            .order_by("pk")
        }
        if locked_products.keys() != {product_id for product_id, _variant_id in requested_quantities}:
            raise serializers.ValidationError(
                "Un article du panier n'est plus disponible."
            )

        requested_variant_ids = {variant_id for _product_id, variant_id in requested_quantities if variant_id}
        locked_variants = {
            variant.pk: variant
            for variant in ProductVariant.objects.select_for_update()
            .filter(pk__in=requested_variant_ids)
            .order_by("pk")
        }
        if locked_variants.keys() != requested_variant_ids:
            raise serializers.ValidationError("Une variante du panier n'est plus disponible.")

        requested_negotiation_ids = {
            negotiation_id for negotiation_id in negotiation_ids.values() if negotiation_id
        }
        locked_negotiations = {
            negotiation.pk: negotiation
            for negotiation in Negotiation.objects.select_for_update()
            .filter(pk__in=requested_negotiation_ids)
            .order_by("pk")
        }
        if locked_negotiations.keys() != requested_negotiation_ids:
            raise serializers.ValidationError("Une réservation de négociation n'est plus disponible.")

        items_data = []
        for line_key, quantity in requested_quantities.items():
            product_id, variant_id = line_key
            product = locked_products[product_id]
            variant = locked_variants.get(variant_id)
            negotiation_id = negotiation_ids.get(line_key)
            negotiation = locked_negotiations.get(negotiation_id)
            expected_unit_price, expected_shipping_cost = expected_prices[line_key]
            if (
                expected_unit_price is not None
                and expected_unit_price != (
                    negotiation.accepted_price if negotiation else product.price
                )
            ) or (
                expected_shipping_cost is not None
                and expected_shipping_cost != product.shipping_cost
            ):
                raise serializers.ValidationError(
                    f"Le prix ou les frais de livraison de « {product.title} » ont changé. "
                    "Actualisez votre panier avant de commander."
                )
            if product.status == Product.Status.ARCHIVED or not product.is_available:
                raise serializers.ValidationError(
                    f"« {product.title} » n'est plus disponible."
                )
            if negotiation:
                if (
                    negotiation.status != Negotiation.Status.ACCEPTED
                    or negotiation.buyer_id != buyer.pk
                    or negotiation.product_id != product.pk
                    or negotiation.variant_id != (variant.pk if variant else None)
                    or negotiation.reserved_until is None
                    or negotiation.reserved_until <= timezone.now()
                    or quantity != 1
                ):
                    raise serializers.ValidationError(
                        "La réservation de cette offre a expiré ou n'est plus valide."
                    )
            available_stock = variant.stock_quantity if variant else product.stock_quantity
            reservations = Negotiation.objects.filter(
                product=product,
                variant=variant if variant else None,
                status=Negotiation.Status.ACCEPTED,
                reserved_until__gt=timezone.now(),
            )
            if negotiation:
                reservations = reservations.exclude(pk=negotiation.pk)
            available_stock -= reservations.count()
            if available_stock < quantity:
                raise serializers.ValidationError(
                    f"Stock insuffisant pour « {product.title} » "
                    f"({available_stock} disponible(s))."
                )
            items_data.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "conversion_visitor_id": conversion_visitors[line_key],
                    "variant": variant,
                    "negotiation": negotiation,
                    "negotiated_unit_price": negotiation.accepted_price if negotiation else None,
                }
            )

        if len({entry["product"].currency for entry in items_data}) > 1:
            raise serializers.ValidationError(
                "Tous les articles d'une commande doivent utiliser la même devise."
            )

        quote = calculate_checkout_quote(
            items_data,
            buyer,
            self.validated_data.get("points_to_redeem", 0),
        )
        quote_by_line = {
            (
                entry["product"].pk,
                entry["variant"].pk if entry["variant"] else None,
            ): entry
            for entry in quote["items"]
        }

        group = CheckoutGroup.objects.create(
            buyer=buyer,
            currency=items_data[0]["product"].currency,
            loyalty_points_redeemed=quote["points_redeemed"],
            loyalty_discount_amount=quote["loyalty_discount"],
        )
        if quote["points_redeemed"]:
            LoyaltyTransaction.objects.create(
                user=buyer,
                checkout_group=group,
                kind=LoyaltyTransaction.Kind.REDEEMED,
                points_delta=-quote["points_redeemed"],
            )
        for entry in items_data:
            product = entry["product"]
            if product.item_type == Product.ItemType.SERVICE:
                continue
            if entry["variant"]:
                updated_variant = ProductVariant.objects.filter(
                    pk=entry["variant"].pk,
                    stock_quantity__gte=entry["quantity"],
                ).update(stock_quantity=F("stock_quantity") - entry["quantity"])
                if updated_variant != 1:
                    raise serializers.ValidationError(
                        f"Le stock de la variante « {entry['variant'].label} » vient de changer. Actualisez votre panier."
                    )
            reserved = Product.objects.filter(
                pk=product.pk,
                status=Product.Status.PUBLISHED,
                moderation_status=Product.ModerationStatus.APPROVED,
                is_suspended=False,
                stock_quantity__gte=entry["quantity"],
            ).update(stock_quantity=F("stock_quantity") - entry["quantity"])
            if reserved != 1:
                raise serializers.ValidationError(
                    f"Le stock de « {product.title} » vient de changer. Actualisez votre panier."
                )
            Product.objects.filter(pk=product.pk, stock_quantity=0).update(
                status=Product.Status.SOLD
            )

        items_by_seller = {}
        for entry in items_data:
            items_by_seller.setdefault(entry["product"].seller_id, []).append(entry)

        for seller_id, seller_entries in items_by_seller.items():
            has_delivery = any(
                entry["product"].sale_method == Product.SaleMethod.DELIVERY
                for entry in seller_entries
            )
            order = Order.objects.create(
                buyer=buyer,
                checkout_group=group,
                shipping_address=(
                    self.validated_data["shipping_address"] if has_delivery else ""
                ),
                shipping_address_record=(
                    self.validated_data.get("shipping_address_record")
                    if has_delivery
                    else None
                ),
                currency=group.currency,
                loyalty_points_redeemed=sum(
                    quote_by_line[(entry["product"].pk, entry["variant"].pk if entry["variant"] else None)]["loyalty_points_redeemed"]
                    for entry in seller_entries
                ),
                loyalty_discount_amount=sum(
                    (quote_by_line[(entry["product"].pk, entry["variant"].pk if entry["variant"] else None)]["loyalty_discount"] for entry in seller_entries),
                    Decimal("0.00"),
                ),
                payment_method=(
                    Order.PaymentMethod.MOBILE_MONEY
                    if settings.PAYMENTS_MODE == "online"
                    else Order.PaymentMethod.CASH
                ),
            )
            order_items = []
            for entry in seller_entries:
                quote_item = quote_by_line[(
                    entry["product"].pk,
                    entry["variant"].pk if entry["variant"] else None,
                )]
                order_items.append(OrderItem(
                    order=order,
                    product=entry["product"],
                    negotiation=entry["negotiation"],
                    seller=entry["product"].seller,
                    product_title=entry["product"].title,
                    variant=entry["variant"],
                    variant_label=entry["variant"].label if entry["variant"] else "",
                    quantity=entry["quantity"],
                    conversion_visitor_id=entry["conversion_visitor_id"],
                    unit_price=quote_item["unit_price"],
                    original_unit_price=quote_item["original_unit_price"],
                    promotion_discount=quote_item["promotion_discount"],
                    promotion_name=quote_item["promotion_name"],
                    loyalty_discount=quote_item["loyalty_discount"],
                    loyalty_points_redeemed=quote_item["loyalty_points_redeemed"],
                    shipping_cost=(
                        quote_item["shipping_cost"]
                        if entry["product"].sale_method == Product.SaleMethod.DELIVERY
                        else 0
                    ),
                    original_shipping_cost=(
                        entry["product"].shipping_cost
                        if entry["product"].sale_method == Product.SaleMethod.DELIVERY
                        else 0
                    ),
                    sale_method=entry["product"].sale_method,
                ))
            OrderItem.objects.bulk_create(order_items)
            for entry in seller_entries:
                negotiation = entry["negotiation"]
                if negotiation is None:
                    continue
                negotiation.status = Negotiation.Status.COMPLETED
                negotiation.save(update_fields=["status", "updated_at"])
                NegotiationEvent.objects.create(
                    negotiation=negotiation,
                    actor=buyer,
                    kind=NegotiationEvent.Kind.CHECKOUT,
                    amount=negotiation.accepted_price,
                )
            movements = []
            for entry in seller_entries:
                if entry["product"].item_type == Product.ItemType.SERVICE:
                    continue
                movements.append(
                    StockMovement(
                        product=entry["product"],
                        variant=entry["variant"],
                        variant_label=entry["variant"].label if entry["variant"] else "",
                        product_title=entry["product"].title,
                        actor=buyer,
                        order=order,
                        movement_type=StockMovement.MovementType.SALE,
                        quantity_delta=-entry["quantity"],
                    )
                )
            StockMovement.objects.bulk_create(movements)
            order.recalculate_total()
            titles = ", ".join(entry["product"].title for entry in seller_entries)
            notify(
                seller_entries[0]["product"].seller,
                Notification.NotificationType.NEW_SALE,
                "Nouvelle commande reçue",
                f"{buyer.username} a commandé : {titles}.",
                "/vendeur?section=sales",
            )

        group.total_amount = sum(
            (order.total_amount for order in group.orders.all()), Decimal("0.00")
        )
        group.save(update_fields=["total_amount"])
        return group


class OrderCancelSerializer(serializers.Serializer):
    """Annulation — aucune donnée d'entrée ; la commande est passée dans le contexte."""

    def validate(self, attrs):
        order = self.context["order"]
        if (
            order.status != Order.Status.PENDING
            or order.items.filter(is_shipped=True).exists()
        ):
            raise serializers.ValidationError(
                "Une commande ne peut être annulée qu'avant le début de son expédition."
            )
        return attrs

    @transaction.atomic
    def save(self):
        order = Order.objects.select_for_update().get(pk=self.context["order"].pk)
        if (
            order.status != Order.Status.PENDING
            or order.items.filter(is_shipped=True).exists()
        ):
            raise serializers.ValidationError(
                "Une commande ne peut être annulée qu'avant le début de son expédition."
            )

        order_items = list(order.items.select_related("product").all())
        product_ids = {
            item.product_id
            for item in order_items
            if item.product_id
            and item.product.item_type == Product.ItemType.PRODUCT
        }
        locked_products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }
        variant_ids = {item.variant_id for item in order_items if item.variant_id}
        locked_variants = {
            variant.pk: variant
            for variant in ProductVariant.objects.select_for_update()
            .filter(pk__in=variant_ids)
            .order_by("pk")
        }
        movements = []
        for item in order_items:
            if not item.product_id or item.product.item_type == Product.ItemType.SERVICE:
                continue
            product = locked_products.get(item.product_id)
            if not product:
                continue
            restored_status = product.status
            if (
                product.status == Product.Status.SOLD
                and product.moderation_status == Product.ModerationStatus.APPROVED
            ):

                restored_status = Product.Status.PUBLISHED
            Product.objects.filter(pk=product.pk).update(
                stock_quantity=F("stock_quantity") + item.quantity,
                status=restored_status,
            )
            variant = locked_variants.get(item.variant_id)
            if variant:
                ProductVariant.objects.filter(pk=variant.pk).update(
                    stock_quantity=F("stock_quantity") + item.quantity
                )
            movements.append(
                StockMovement(
                    product=product,
                    variant=variant,
                    variant_label=item.variant_label,
                    product_title=item.product_title,
                    actor=order.buyer,
                    order=order,
                    movement_type=StockMovement.MovementType.CANCELLATION,
                    quantity_delta=item.quantity,
                )
            )
        StockMovement.objects.bulk_create(movements)

        order.payments.filter(status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED
        )
        points_to_restore = sum(item.loyalty_points_redeemed for item in order_items)
        if points_to_restore:
            LoyaltyTransaction.objects.get_or_create(
                user=order.buyer,
                order=order,
                kind=LoyaltyTransaction.Kind.REFUNDED,
                defaults={
                    "checkout_group": order.checkout_group,
                    "points_delta": points_to_restore,
                },
            )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return order
