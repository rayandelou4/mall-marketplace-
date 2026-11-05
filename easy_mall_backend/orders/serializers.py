"""
Serializers de l'app `orders`.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from catalog.models import Product
from notifications.models import Notification
from notifications.services import notify
from payments.models import Payment
from localization.models import PrivateAddress

from .models import Order, OrderItem


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

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "order_status",
            "order_created_at",
            "product",
            "product_title",
            "seller_username",
            "quantity",
            "unit_price",
            "shipping_cost",
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
            "created_at",
        ]

    def get_sellers(self, obj):
        return list(obj.items.values_list("seller__username", flat=True).distinct())


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "payment_method",
            "total_amount",
            "currency",
            "shipping_address",
            "items",
            "created_at",
            "updated_at",
        ]


class OrderCreateSerializer(serializers.Serializer):
    """
    Création d'une commande à partir du panier (checkout).
    Chaque ligne fige le titre/prix du produit au moment de l'achat — voir
    `OrderItem.product_title` / `unit_price` dans le modèle.
    """

    shipping_address = serializers.CharField(required=False, allow_blank=False)
    private_address_id = serializers.UUIDField(required=False, write_only=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate(self, attrs):
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

    def validate_items(self, value):
        requested_quantities = {}
        expected_prices = {}
        for entry in value:
            try:
                product_id = uuid.UUID(str(entry["product_id"]))
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
            requested_quantities[product_id] = (
                requested_quantities.get(product_id, 0) + quantity
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
                product_id in expected_prices
                and expected_prices[product_id] != expected
            ):
                raise serializers.ValidationError(
                    "Les informations de prix sont incohérentes pour un même article."
                )
            expected_prices[product_id] = expected

        products = {
            product.pk: product
            for product in Product.objects.select_related("seller").filter(
                pk__in=requested_quantities
            )
        }
        missing_ids = requested_quantities.keys() - products.keys()
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
        for product_id, quantity in requested_quantities.items():
            product = products[product_id]
            expected_unit_price, expected_shipping_cost = expected_prices[product_id]
            if (
                expected_unit_price is not None and expected_unit_price != product.price
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
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(
                    f"Stock insuffisant pour « {product.title} » "
                    f"({product.stock_quantity} disponible(s))."
                )

            cleaned.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "expected_unit_price": expected_unit_price,
                    "expected_shipping_cost": expected_shipping_cost,
                }
            )
        return cleaned

    @transaction.atomic
    def save(self):
        buyer = self.context["request"].user
        requested_items = self.validated_data["items"]
        requested_quantities = {
            entry["product"].pk: entry["quantity"] for entry in requested_items
        }
        expected_prices = {
            entry["product"].pk: (
                entry["expected_unit_price"],
                entry["expected_shipping_cost"],
            )
            for entry in requested_items
        }
        locked_products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .select_related("seller")
            .filter(pk__in=requested_quantities)
            .order_by("pk")
        }
        if locked_products.keys() != requested_quantities.keys():
            raise serializers.ValidationError(
                "Un article du panier n'est plus disponible."
            )

        items_data = []
        for product_id, quantity in requested_quantities.items():
            product = locked_products[product_id]
            expected_unit_price, expected_shipping_cost = expected_prices[product_id]
            if (
                expected_unit_price is not None and expected_unit_price != product.price
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
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(
                    f"Stock insuffisant pour « {product.title} » "
                    f"({product.stock_quantity} disponible(s))."
                )
            items_data.append({"product": product, "quantity": quantity})

        if len({entry["product"].currency for entry in items_data}) > 1:
            raise serializers.ValidationError(
                "Tous les articles d'une commande doivent utiliser la même devise."
            )

        order = Order.objects.create(
            buyer=buyer,
            shipping_address=self.validated_data["shipping_address"],
            shipping_address_record=self.validated_data.get("shipping_address_record"),
            currency=items_data[0]["product"].currency,
            payment_method=(
                Order.PaymentMethod.MOBILE_MONEY
                if settings.PAYMENTS_MODE == "online"
                else Order.PaymentMethod.CASH
            ),
        )

        order_items = [
            OrderItem(
                order=order,
                product=entry["product"],
                seller=entry["product"].seller,
                product_title=entry["product"].title,
                quantity=entry["quantity"],
                unit_price=entry["product"].price,
                shipping_cost=(
                    entry["product"].shipping_cost
                    if entry["product"].sale_method == Product.SaleMethod.DELIVERY
                    else 0
                ),
                sale_method=entry["product"].sale_method,
            )
            for entry in items_data
        ]
        OrderItem.objects.bulk_create(order_items)

        for entry in items_data:
            product = entry["product"]
            remaining_stock = product.stock_quantity - entry["quantity"]
            update_fields = {"stock_quantity": F("stock_quantity") - entry["quantity"]}
            # Stock épuisé : on sort l'annonce du statut "published" tout de
            # suite, sinon elle resterait visible dans le catalogue public
            # (is_available vérifie stock_quantity, mais pas le queryset de liste).
            if remaining_stock <= 0:
                update_fields["status"] = Product.Status.SOLD
            Product.objects.filter(pk=product.pk).update(**update_fields)

        order.recalculate_total()

        seller_items = {}
        for entry in items_data:
            seller = entry["product"].seller
            seller_items.setdefault(seller.pk, {"seller": seller, "titles": []})[
                "titles"
            ].append(entry["product"].title)
        for seller_data in seller_items.values():
            titles = ", ".join(seller_data["titles"])
            notify(
                seller_data["seller"],
                Notification.NotificationType.NEW_SALE,
                "Nouvelle commande reçue",
                f"{buyer.username} a commandé : {titles}.",
                "/vendeur?section=sales",
            )
        return order


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
        product_ids = {item.product_id for item in order_items if item.product_id}
        locked_products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }
        for item in order_items:
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

        order.payments.filter(status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED
        )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return order
