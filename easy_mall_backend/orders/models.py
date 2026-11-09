"""
Modèles de l'app `orders`.

Une commande peut regrouper des articles de plusieurs vendeurs différents
(comme sur Vinted) : `OrderItem` porte donc son propre `seller`, dénormalisé,
pour permettre à chaque vendeur de suivre ses ventes sans avoir à parcourir
toute la commande.
"""

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class CheckoutGroup(models.Model):
    """Regroupe les commandes vendeur issues d'une validation de panier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="checkout_groups"
    )
    currency = models.CharField(max_length=3)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    buyer_purchase_counted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checkout_groups"
        ordering = ["-created_at"]


class Order(models.Model):
    """Commande passée par un acheteur — peut contenir des articles de plusieurs vendeurs."""

    class PaymentMethod(models.TextChoices):
        CASH = "cash", _("Espèces à la réception")
        MOBILE_MONEY = "mobile_money", _("Mobile Money")

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente de remise")
        PAID = "paid", _("Payée")
        SHIPPED = "shipped", _("Expédiée")
        DELIVERED = "delivered", _("Livrée")
        CANCELLED = "cancelled", _("Annulée")
        DISPUTED = "disputed", _("En litige")
        REFUNDED = "refunded", _("Remboursée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT : on ne supprime jamais un compte ayant un historique de commandes
    # (traçabilité comptable) — préférer une désactivation (`User.is_active=False`).
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    checkout_group = models.ForeignKey(
        CheckoutGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    hidden_by_buyer = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    shipping_address = models.TextField(blank=True)
    shipping_address_record = models.ForeignKey(
        "localization.PrivateAddress",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        verbose_name = _("commande")
        verbose_name_plural = _("commandes")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "status"]),
        ]

    def __str__(self):
        return f"Commande {self.id} — {self.get_status_display()}"

    @property
    def items_count(self):
        return self.items.count()

    def recalculate_total(self, save=True):
        """Recalcule `total_amount` à partir des lignes — à appeler après tout ajout/retrait d'item."""
        total = sum((item.subtotal for item in self.items.all()), start=0)
        self.total_amount = total
        if save:
            self.save(update_fields=["total_amount"])
        return total


class OrderItem(models.Model):
    """
    Ligne de commande. Le titre et le prix sont figés au moment de l'achat
    (`product_title`, `unit_price`) pour que la commande reste lisible même si
    le produit est modifié ou supprimé par la suite.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    # SET_NULL : la ligne de commande doit survivre à la suppression du produit.
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    variant_label = models.CharField(max_length=100, blank=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sold_order_items",
    )

    product_title = models.CharField(max_length=150)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    conversion_visitor_id = models.UUIDField(null=True, blank=True, db_index=True)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sale_method = models.CharField(
        max_length=10,
        choices=[("delivery", _("Livraison")), ("pickup", _("Remise en main propre"))],
        default="delivery",
    )
    is_shipped = models.BooleanField(default=False)
    hidden_by_seller = models.BooleanField(default=False)

    class Meta:
        db_table = "order_items"
        verbose_name = _("ligne de commande")
        verbose_name_plural = _("lignes de commande")

    def __str__(self):
        return f"{self.product_title} x{self.quantity}"

    def save(self, *args, **kwargs):
        if not self.product_title and self.product_id:
            self.product_title = self.product.title
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.unit_price * self.quantity) + self.shipping_cost
