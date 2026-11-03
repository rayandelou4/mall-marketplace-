"""
Serializers de l'app `catalog`.
"""

from rest_framework import serializers
from accounts.models import User

from .models import (
    Category,
    Favorite,
    Product,
    ProductImage,
    ProductVideo,
    SavedSearch,
    SellerFavorite,
)


def _public_seller_city(product):
    location = getattr(product.seller, "public_location", None)
    preference = getattr(product.seller, "location_preference", None)
    if (
        location is None
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
    if location is None or (preference is not None and not preference.show_country):
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


class ProductComparisonSerializer(serializers.ModelSerializer):
    """
    Une ligne du comparateur de prix : une offre équivalente chez un autre
    vendeur. Le délai de livraison est une estimation simple (même ville que
    l'annonce de référence = plus rapide) — pas de vraie logistique/distance,
    volontairement simplifié.
    """

    primary_image = serializers.SerializerMethodField()
    condition_display = serializers.CharField(
        source="get_condition_display", read_only=True
    )
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    # seller_phone_number = serializers.SerializerMethodField()
    seller_rating = serializers.DecimalField(
        source="seller.average_rating", max_digits=3, decimal_places=2, read_only=True
    )
    estimated_delivery = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()

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
            "estimated_delivery",
            "primary_image",
        ]

    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        return image.image_url if image else None

    def get_city(self, obj):
        return _public_seller_city(obj)

    def get_estimated_delivery(self, obj):
        reference_city = (self.context.get("reference_city") or "").strip().lower()
        if reference_city and obj.city.strip().lower() == reference_city:
            return "1-2 jours"
        return "3-5 jours"


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
            "city",
            "seller_location_display",
            "primary_image",
            "views_count",
            "favorites_count",
            "seller_username",
            "seller_avatar_url",
            "seller_rating",
            "status",
            "moderation_status",
            "created_at",
        ]

    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        return image.image_url if image else None

    def get_seller_location_display(self, obj):
        location = getattr(obj.seller, "public_location", None)
        return location.display_name if location is not None else ""

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
            "shipping_cost",
            "seller_location_display",
            "status",
            "moderation_status",
            "is_available",
            "views_count",
            "favorites_count",
            "category",
            "category_name",
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
        if request and request.user.is_authenticated:
            return obj.seller.phone_number
        return None

    def get_seller_location_display(self, obj):
        location = getattr(obj.seller, "public_location", None)
        return location.display_name if location is not None else ""

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
            "shipping_cost",
            "status",
            "images",
        ]

    def validate(self, attrs):
        item_type = attrs.get(
            "item_type", getattr(self.instance, "item_type", Product.ItemType.PRODUCT)
        )
        if item_type == Product.ItemType.SERVICE:
            attrs["condition"] = ""
            attrs["stock_quantity"] = 1
            attrs["shipping_cost"] = 0
        elif not attrs.get("condition", getattr(self.instance, "condition", "")):
            raise serializers.ValidationError(
                {"condition": "L'état est obligatoire pour un produit."}
            )
        return attrs

    def validate_images(self, value):
        if len(value) > ProductImage.MAX_IMAGES_PER_PRODUCT:
            raise serializers.ValidationError(
                f"Maximum {ProductImage.MAX_IMAGES_PER_PRODUCT} images par produit."
            )
        return value

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        if validated_data.get("status") in (
            Product.Status.PUBLISHED,
            Product.Status.ARCHIVED,
        ):
            validated_data["moderation_status"] = Product.ModerationStatus.APPROVED
        product = Product.objects.create(
            seller=self.context["request"].user, **validated_data
        )
        self._save_images(product, images)
        return product

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)
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
    seller_full_name = serializers.CharField(source="seller.full_name", read_only=True)
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
            "seller_full_name",
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
