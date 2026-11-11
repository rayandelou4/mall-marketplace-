from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Promotion(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", _("Pourcentage")
        FIXED = "fixed", _("Montant fixe par article")
        SALE_PRICE = "sale_price", _("Prix promotionnel")

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="promotions"
    )
    products = models.ManyToManyField("catalog.Product", related_name="promotions")
    name = models.CharField(max_length=120)
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, blank=True)
    min_quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    min_customer_purchases = models.PositiveIntegerField(default=0)
    free_shipping = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(
            fields=["seller", "is_active", "starts_at", "ends_at"],
            name="promotions_seller_62ac06_idx",
        )]

    def __str__(self):
        return self.name


class LoyaltyProgram(models.Model):
    """Règles globales uniques, modifiables depuis l'administration Django."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    is_active = models.BooleanField(default=True)
    points_per_currency_unit = models.DecimalField(
        max_digits=7, decimal_places=2, default=1, validators=[MinValueValidator(0)]
    )
    redemption_value_per_point = models.DecimalField(
        max_digits=9, decimal_places=4, default="0.01", validators=[MinValueValidator(0)]
    )
    max_redemption_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    currency_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Surcharges de taux par devise : points_per_currency_unit et redemption_value_per_point.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Règles globales de fidélité"


class LoyaltyTransaction(models.Model):
    class Kind(models.TextChoices):
        EARNED = "earned", _("Points gagnés")
        REDEEMED = "redeemed", _("Points utilisés")
        REFUNDED = "refunded", _("Points recrédités")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="loyalty_transactions"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    points_delta = models.IntegerField()
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True,
        related_name="loyalty_transactions",
    )
    checkout_group = models.ForeignKey(
        "orders.CheckoutGroup", on_delete=models.PROTECT, null=True, blank=True,
        related_name="loyalty_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "kind"], condition=models.Q(order__isnull=False),
                name="unique_loyalty_entry_per_order",
            ),
            models.UniqueConstraint(
                fields=["checkout_group", "kind"],
                condition=models.Q(checkout_group__isnull=False, kind="redeemed"),
                name="unique_loyalty_redemption_per_checkout",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.points_delta:+d} points"