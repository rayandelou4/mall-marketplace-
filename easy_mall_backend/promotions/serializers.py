from decimal import Decimal

from rest_framework import serializers

from catalog.models import Product

from .models import Promotion


class PromotionSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Product.objects.all(), allow_empty=False
    )

    class Meta:
        model = Promotion
        fields = [
            "id", "name", "products", "discount_type", "value", "currency",
            "min_quantity", "min_customer_purchases", "free_shipping",
            "starts_at", "ends_at", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        products = attrs.get("products")
        if products is None and self.instance:
            products = list(self.instance.products.all())
        products = products or []
        seller = self.context["request"].user
        if any(product.seller_id != seller.pk for product in products):
            raise serializers.ValidationError({"products": "Une promotion ne peut concerner que vos annonces."})
        discount_type = attrs.get("discount_type", getattr(self.instance, "discount_type", None))
        value = attrs.get("value", getattr(self.instance, "value", Decimal("0")))
        currency = attrs.get("currency", getattr(self.instance, "currency", ""))
        free_shipping = attrs.get("free_shipping", getattr(self.instance, "free_shipping", False))
        if discount_type == Promotion.DiscountType.PERCENTAGE and not (
            Decimal("0") <= value <= Decimal("100")
            and (value > 0 or free_shipping)
        ):
            raise serializers.ValidationError({"value": "Le pourcentage doit être supérieur à 0 et inférieur ou égal à 100."})
        if discount_type == Promotion.DiscountType.PERCENTAGE:
            attrs["currency"] = ""
        if discount_type in {Promotion.DiscountType.FIXED, Promotion.DiscountType.SALE_PRICE}:
            product_currencies = {product.currency for product in products}
            if len(product_currencies) > 1:
                raise serializers.ValidationError({"products": "Les offres à montant fixe doivent utiliser une seule devise."})
            expected_currency = next(iter(product_currencies), "")
            if currency and expected_currency and currency != expected_currency:
                raise serializers.ValidationError({"currency": "La devise doit correspondre aux annonces sélectionnées."})
            if not currency:
                attrs["currency"] = expected_currency
            if value <= 0:
                raise serializers.ValidationError({"value": "Le montant doit être supérieur à zéro."})
            if discount_type == Promotion.DiscountType.SALE_PRICE and any(value >= product.price for product in products):
                raise serializers.ValidationError({"value": "Le prix promotionnel doit être inférieur au prix de chaque annonce sélectionnée."})
        if not value and not free_shipping:
            raise serializers.ValidationError({"value": "Ajoutez une remise ou activez la livraison gratuite."})
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "La date de fin doit suivre la date de début."})
        return attrs