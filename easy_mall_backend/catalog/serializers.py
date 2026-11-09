"""
Serializers de l'app `catalog`.
"""

from rest_framework import serializers
from django.db import transaction
from accounts.models import User

from .models import (
    Category,
    Favorite,
    Product,
    ProductVariant,
    ProductImage,
    ProductIdentity,
    StockMovement,
    ProductVideo,
    SavedSearch,
    SellerFavorite,
)


def _public_seller_city(product):
    location = getattr(product.seller, "public_location", None)
    preference = getattr(product.seller, "location_preference", None)
    if (
        location is None
        or not location.is_active
        or preference is None
        or not preference.show_locality
        or location.precision
        not in {location.Precision.CITY, location.Precision.LOCALITY}
        or location.locality is None
        or (
            location.locality.level == "neighborhood"
            and location.precision != location.Precision.LOCALITY
        )
    ):
        return ""
    return location.locality.name


def _public_seller_country(product):
    location = getattr(product.seller, "public_location", None)
    preference = getattr(product.seller, "location_preference", None)
    if location is None or not location.is_active or (preference is not None and not preference.show_country):
        return ""
    return location.country.name


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "icon_url", "order", "children"]

    def get_children(self, obj):
        return CategorySerializer(obj.children.filter(is_active=True), many=True).data


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "order", "is_primary"]


class ProductVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVideo
        fields = ["video_url"]


class ProductIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductIdentity
        fields = ["id", "name", "brand", "model_name", "manufacturer_reference", "variant"]


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "label", "attributes", "stock_quantity"]
        read_only_fields = fields


class ProductComparisonSerializer(serializers.ModelSerializer):
    """Offre d'une identité produit validée, avec livraison non extrapolée."""

    primary_image = serializers.SerializerMethodField()
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    # seller_phone_number = serializers.SerializerMethodField()
    seller_rating = serializers.DecimalField(
        source="seller.average_rating", max_digits=3, decimal_places=2, read_only=True
    )
    city = serializers.SerializerMethodField()
    shipping_cost_known = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "price",
            "currency",
            "city",
            "condition_display",
            "seller_username",
            "seller_rating",
            "shipping_cost",
            "shipping_cost_known",
            "is_available",
            "primary_image",
        ]

    def get_primary_image(self, obj):
        images = list(obj.images.all())
        image = next((item for item in images if item.is_primary), None)
        image = image or (images[0] if images else None)
        return image.image_url if image else None

    def get_city(self, obj):
        return _public_seller_city(obj)

    def get_shipping_cost_known(self, obj):
        return obj.shipping_cost > 0


class ProductListSerializer(serializers.ModelSerializer):
    """Version allégée pour le catalogue/les listes (performance)."""

    primary_image = serializers.SerializerMethodField()
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    price_unit_display = serializers.CharField(
        source="get_price_unit_display", read_only=True
    )
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    seller_avatar_url = serializers.URLField(
        source="seller.avatar_url", read_only=True, allow_null=True
    )
    seller_rating = serializers.DecimalField(
        source="seller.average_rating", max_digits=3, decimal_places=2, read_only=True
    )
    seller_location_display = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    comparison_identity = ProductIdentitySerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    comparison_offer_count = serializers.IntegerField(read_only=True, allow_null=True, default=None)
    comparison_seller_count = serializers.IntegerField(read_only=True, allow_null=True, default=None)
    comparison_lowest_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "item_type",
            "title",
            "price",
            "currency",
            "price_unit",
            "price_unit_display",
            "condition",
            "condition_display",
            "category",
            "category_name",
            "stock_quantity",
            "variants",
            "sale_method",
            "city",
            "seller_location_display",
            "primary_image",
            "views_count",
            "favorites_count",
            "seller_username",
            "seller_avatar_url",
            "seller_rating",
            "comparison_identity",
            "comparison_offer_count",
            "comparison_seller_count",
            "comparison_lowest_price",
            "status",
            "moderation_status",
            "created_at",
        ]

    def get_primary_image(self, obj):
        images = list(obj.images.all())
        image = next((item for item in images if item.is_primary), None)
        image = image or (images[0] if images else None)
        return image.image_url if image else None

    def get_seller_location_display(self, obj):
        location = getattr(obj.seller, "public_location", None)
        return location.display_name if location is not None and location.is_active else ""

    def get_city(self, obj):
        return _public_seller_city(obj)


class ProductDetailSerializer(serializers.ModelSerializer):
    """Version complète pour la fiche produit."""

    images = ProductImageSerializer(many=True, read_only=True)
    video = ProductVideoSerializer(read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    seller_phone_number = serializers.SerializerMethodField()
    seller_rating = serializers.DecimalField(
        source="seller.average_rating", max_digits=3, decimal_places=2, read_only=True
    )
    seller_total_sales = serializers.IntegerField(
        source="seller.total_sales", read_only=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    price_unit_display = serializers.CharField(
        source="get_price_unit_display", read_only=True
    )
    is_available = serializers.ReadOnlyField()
    seller_location_display = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    comparison_identity = ProductIdentitySerializer(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "item_type",
            "title",
            "description",
            "price",
            "currency",
            "price_unit",
            "price_unit_display",
            "condition",
            "condition_display",
            "city",
            "country",
            "stock_quantity",
            "variants",
            "shipping_cost",
            "sale_method",
            "seller_location_display",
            "status",
            "moderation_status",
            "is_available",
            "views_count",
            "favorites_count",
            "category",
            "category_name",
            "comparison_identity",
            "images",
            "video",
            "seller_username",
            "seller_phone_number",
            "seller_rating",
            "seller_total_sales",
            "created_at",
            "updated_at",
        ]

    def get_seller_phone_number(self, obj):
        request = self.context.get("request")
        if (
            request
            and request.user.is_authenticated
            and obj.seller.show_phone_on_listings
        ):
            return obj.seller.phone_number
        return None

    def get_seller_location_display(self, obj):
        location = getattr(obj.seller, "public_location", None)
        return location.display_name if location is not None and location.is_active else ""

    def get_city(self, obj):
        return _public_seller_city(obj)

    def get_country(self, obj):
        return _public_seller_country(obj)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Création/édition d'une annonce par son propriétaire.
    `images` : liste d'URLs déjà uploadées vers Cloudinary/S3 par le
    frontend (upload direct hors de ce serializer) — max 3 (cahier des charges).
    """

    images = serializers.ListField(
        child=serializers.URLField(),
        write_only=True,
        required=False,
        max_length=ProductImage.MAX_IMAGES_PER_PRODUCT,
    )
    expected_stock_quantity = serializers.IntegerField(
        write_only=True, required=False, min_value=0
    )
    variants = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "item_type",
            "title",
            "description",
            "category",
            "price",
            "currency",
            "price_unit",
            "condition",
            "city",
            "country",
            "stock_quantity",
            "expected_stock_quantity",
            "variants",
            "shipping_cost",
            "sale_method",
            "status",
            "images",
        ]

    def validate(self, attrs):
        variants = attrs.get("variants")
        item_type = attrs.get(
            "item_type", getattr(self.instance, "item_type", Product.ItemType.PRODUCT)
        )
        if variants is not None:
            if item_type != Product.ItemType.PRODUCT:
                raise serializers.ValidationError({"variants": "Les services ne prennent pas en charge les variantes de stock."})
            labels = []
            total_stock = 0
            clean_variants = []
            for variant in variants:
                label = str(variant.get("label", "")).strip()
                attributes = variant.get("attributes", {})
                try:
                    quantity = int(variant.get("stock_quantity", 0))
                except (TypeError, ValueError) as exc:
                    raise serializers.ValidationError({"variants": "Quantité de variante invalide."}) from exc
                if not label or quantity < 0 or not isinstance(attributes, dict):
                    raise serializers.ValidationError({"variants": "Chaque variante doit avoir un nom, des attributs et une quantité positive ou nulle."})
                if label in labels:
                    raise serializers.ValidationError({"variants": "Les noms de variantes doivent être uniques."})
                labels.append(label)
                total_stock += quantity
                clean_variants.append({
                    **({"id": str(variant["id"])} if variant.get("id") else {}),
                    "label": label,
                    "attributes": attributes,
                    "stock_quantity": quantity,
                })
            attrs["variants"] = clean_variants
            attrs["stock_quantity"] = total_stock
        elif (
            self.instance
            and item_type == Product.ItemType.PRODUCT
            and self.instance.variants.exists()
            and "stock_quantity" in attrs
        ):
            raise serializers.ValidationError({"variants": "Modifiez le stock des variantes pour ajuster le stock total."})
        if item_type == Product.ItemType.SERVICE:
            attrs["condition"] = ""
            attrs["stock_quantity"] = 1
            attrs["shipping_cost"] = 0
        elif not attrs.get("condition", getattr(self.instance, "condition", "")):
            raise serializers.ValidationError(
                {"condition": "L'état est obligatoire pour un produit."}
            )
        if (
            self.instance
            and item_type == Product.ItemType.PRODUCT
            and "stock_quantity" in attrs
            and "expected_stock_quantity" not in attrs
        ):
            raise serializers.ValidationError(
                {"expected_stock_quantity": "Rechargez l'annonce avant de modifier le stock."}
            )
        else:
            stock_quantity = attrs.get(
                "stock_quantity", getattr(self.instance, "stock_quantity", 1)
            )
            current_status = attrs.get(
                "status", getattr(self.instance, "status", Product.Status.DRAFT)
            )
            if stock_quantity == 0 and current_status == Product.Status.PUBLISHED:
                attrs["status"] = Product.Status.SOLD
            elif (
                self.instance
                and stock_quantity > 0
                and self.instance.status == Product.Status.SOLD
                and "status" not in attrs
            ):
                attrs["status"] = Product.Status.PUBLISHED
        return attrs

    def validate_images(self, value):
        if len(value) > ProductImage.MAX_IMAGES_PER_PRODUCT:
            raise serializers.ValidationError(
                f"Maximum {ProductImage.MAX_IMAGES_PER_PRODUCT} images par produit."
            )
        return value

    @transaction.atomic
    def create(self, validated_data):
        images = validated_data.pop("images", [])
        variants = validated_data.pop("variants", [])
        validated_data.pop("expected_stock_quantity", None)
        if validated_data.get("status") in (
            Product.Status.PUBLISHED,
            Product.Status.ARCHIVED,
        ):
            validated_data["moderation_status"] = Product.ModerationStatus.APPROVED
        product = Product.objects.create(
            seller=self.context["request"].user, **validated_data
        )
        ProductVariant.objects.bulk_create([
            ProductVariant(product=product, **{key: value for key, value in variant.items() if key != "id"})
            for variant in variants
        ])
        self._save_images(product, images)
        if product.item_type == Product.ItemType.PRODUCT and product.stock_quantity:
            if variants:
                StockMovement.objects.bulk_create([
                    StockMovement(
                        product=product,
                        variant=variant,
                        variant_label=variant.label,
                        product_title=product.title,
                        actor=self.context["request"].user,
                        movement_type=StockMovement.MovementType.OPENING,
                        quantity_delta=variant.stock_quantity,
                    )
                    for variant in product.variants.all()
                    if variant.stock_quantity
                ])
            else:
                StockMovement.objects.create(
                    product=product,
                    product_title=product.title,
                    actor=self.context["request"].user,
                    movement_type=StockMovement.MovementType.OPENING,
                    quantity_delta=product.stock_quantity,
                )
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
        variants = validated_data.pop("variants", None)
        expected_stock_quantity = validated_data.pop("expected_stock_quantity", None)
        if "stock_quantity" in validated_data and expected_stock_quantity is not None:
            instance = Product.objects.select_for_update().get(pk=instance.pk)
            if instance.stock_quantity != expected_stock_quantity:
                raise serializers.ValidationError(
                    {"stock_quantity": "Le stock a changé depuis le chargement. Rechargez l'annonce."}
                )
        previous_stock = instance.stock_quantity
        if validated_data.get("status") in (
            Product.Status.PUBLISHED,
            Product.Status.ARCHIVED,
        ):
            validated_data["moderation_status"] = Product.ModerationStatus.APPROVED
        elif validated_data.get("status") in (
            Product.Status.DRAFT,
            Product.Status.ARCHIVED,
        ):
            validated_data["moderation_status"] = Product.ModerationStatus.PENDING
        instance = super().update(instance, validated_data)
        if instance.item_type == Product.ItemType.SERVICE:
            instance.variants.all().delete()
        if variants is not None:
            existing = {str(item.pk): item for item in instance.variants.select_for_update()}
            retained_ids = set()
            movements = []
            for variant_data in variants:
                variant_data = dict(variant_data)
                variant_id = str(variant_data.pop("id", ""))
                if variant_id in existing:
                    variant = existing[variant_id]
                    previous_quantity = variant.stock_quantity
                    variant.label = variant_data["label"]
                    variant.attributes = variant_data["attributes"]
                    variant.stock_quantity = variant_data["stock_quantity"]
                    variant.save()
                    quantity_delta = variant.stock_quantity - previous_quantity
                    retained_ids.add(variant.pk)
                else:
                    created_variant = ProductVariant.objects.create(product=instance, **variant_data)
                    quantity_delta = created_variant.stock_quantity
                    variant = created_variant
                    retained_ids.add(created_variant.pk)
                if quantity_delta:
                    movements.append(StockMovement(
                        product=instance,
                        variant=variant,
                        variant_label=variant.label,
                        product_title=instance.title,
                        actor=self.context["request"].user,
                        movement_type=StockMovement.MovementType.ADJUSTMENT,
                        quantity_delta=quantity_delta,
                    ))
            for variant in instance.variants.exclude(pk__in=retained_ids):
                if variant.order_items.exists():
                    if variant.stock_quantity:
                        movements.append(StockMovement(
                            product=instance,
                            variant=variant,
                            variant_label=variant.label,
                            product_title=instance.title,
                            actor=self.context["request"].user,
                            movement_type=StockMovement.MovementType.ADJUSTMENT,
                            quantity_delta=-variant.stock_quantity,
                        ))
                        variant.stock_quantity = 0
                        variant.save(update_fields=["stock_quantity", "updated_at"])
                else:
                    variant.delete()
            StockMovement.objects.bulk_create(movements)
        if (
            instance.item_type == Product.ItemType.PRODUCT
            and previous_stock != instance.stock_quantity
            and variants is None
        ):
            StockMovement.objects.create(
                product=instance,
                product_title=instance.title,
                actor=self.context["request"].user,
                movement_type=StockMovement.MovementType.ADJUSTMENT,
                quantity_delta=instance.stock_quantity - previous_stock,
            )
        if images is not None:
            instance.images.all().delete()
            self._save_images(instance, images)
        return instance

    @staticmethod
    def _save_images(product, image_urls):
        ProductImage.objects.bulk_create(
            [
                ProductImage(
                    product=product, image_url=url, order=i, is_primary=(i == 0)
                )
                for i, url in enumerate(image_urls)
            ]
        )


class StockMovementSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product_title",
            "variant_label",
            "actor_username",
            "order",
            "movement_type",
            "quantity_delta",
            "created_at",
        ]
        read_only_fields = fields


class FavoriteSerializer(serializers.ModelSerializer):
    product_detail = ProductListSerializer(source="product", read_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "product", "product_detail", "created_at"]
        extra_kwargs = {"product": {"write_only": True}}

    def validate_product(self, value):
        request = self.context["request"]
        if Favorite.objects.filter(user=request.user, product=value).exists():
            raise serializers.ValidationError("Ce produit est déjà dans vos favoris.")
        return value

    def create(self, validated_data):
        return Favorite.objects.create(
            user=self.context["request"].user, **validated_data
        )


class SellerFavoriteSerializer(serializers.ModelSerializer):
    seller = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), write_only=True
    )
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    seller_avatar_url = serializers.URLField(
        source="seller.avatar_url", read_only=True, allow_null=True
    )
    city = serializers.CharField(source="seller.city", read_only=True)
    country = serializers.CharField(source="seller.country", read_only=True)
    average_rating = serializers.DecimalField(
        source="seller.average_rating", max_digits=3, decimal_places=2, read_only=True
    )

    class Meta:
        model = SellerFavorite
        fields = [
            "id",
            "seller",
            "seller_username",
            "seller_avatar_url",
            "city",
            "country",
            "average_rating",
            "created_at",
        ]

    def validate_seller(self, value):
        request = self.context["request"]
        if value.pk == request.user.pk:
            raise serializers.ValidationError(
                "Vous ne pouvez pas vous ajouter à vos vendeurs favoris."
            )
        if SellerFavorite.objects.filter(user=request.user, seller=value).exists():
            raise serializers.ValidationError("Ce vendeur est déjà dans vos favoris.")
        return value

    def create(self, validated_data):
        return SellerFavorite.objects.create(
            user=self.context["request"].user, **validated_data
        )


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = ["id", "name", "query_params", "created_at"]

    def create(self, validated_data):
        return SavedSearch.objects.create(
            user=self.context["request"].user, **validated_data
        )
