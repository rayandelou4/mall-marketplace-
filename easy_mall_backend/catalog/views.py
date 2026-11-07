"""
Vues de l'app `catalog`.

Nécessite `pip install django-filter` et `django_filters` dans
INSTALLED_APPS pour les filtres du catalogue (catégorie, ville, état,
prix, date d'ajout — cahier des charges §"Catalogue").
"""

import re
import unicodedata

import django_filters
from django.db.models import Case, Count, DecimalField, F, IntegerField, Min, OuterRef, Q, Subquery, Value, When, Window
from django.db.models.functions import RowNumber
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from accounts.models import User
from localization.models import AdministrativeArea, Country, DeliveryOption
from .models import Category, Favorite, Product, SavedSearch, SellerFavorite
from .serializers import (
    CategorySerializer,
    FavoriteSerializer,
    ProductComparisonSerializer,
    ProductCreateUpdateSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    SavedSearchSerializer,
    SellerFavoriteSerializer,
)

# Mots trop courants pour compter dans le rapprochement "titre similaire" du
# comparateur de prix (voir ProductViewSet.comparisons ci-dessous).
_STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "des",
    "du",
    "un",
    "une",
    "et",
    "en",
    "pour",
    "avec",
    "sur",
    "dans",
    "au",
    "aux",
    "ce",
    "cette",
    "ces",
    "à",
}


def _significant_words(title):
    """Mots de 3+ lettres/chiffres, hors mots vides — base du rapprochement."""
    normalized = unicodedata.normalize("NFKD", title).casefold()
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    words = re.findall(r"[a-z0-9]+", normalized)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Seul le vendeur propriétaire peut modifier/supprimer son annonce."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.seller_id == request.user.id

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class ProductFilter(django_filters.FilterSet):
    """GET products: category, search, city, condition, item_type, price_min/max, currency, seller_type, available and ordering."""

    price_min = django_filters.NumberFilter(
        field_name="price", lookup_expr="gte", min_value=0
    )
    price_max = django_filters.NumberFilter(
        field_name="price", lookup_expr="lte", min_value=0
    )
    added_after = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    city = django_filters.CharFilter(method="filter_city")
    country = django_filters.CharFilter(method="filter_public_country")
    administrative_area = django_filters.UUIDFilter(method="filter_public_area")
    locality = django_filters.UUIDFilter(method="filter_public_locality")
    delivery_mode = django_filters.ChoiceFilter(
        choices=DeliveryOption.Mode.choices,
        method="filter_delivery_mode",
    )
    pickup_available = django_filters.BooleanFilter(method="filter_pickup_available")
    delivery_area = django_filters.UUIDFilter(method="filter_delivery_area")
    seller = django_filters.CharFilter(field_name="seller__username")
    seller_type = django_filters.ChoiceFilter(
        field_name="seller__seller_type", choices=User.SellerType.choices
    )
    condition = django_filters.ChoiceFilter(choices=Product.Condition.choices)
    item_type = django_filters.ChoiceFilter(choices=Product.ItemType.choices)
    currency = django_filters.CharFilter(
        field_name="currency", lookup_expr="iexact", max_length=3
    )
    available = django_filters.BooleanFilter(method="filter_available")

    class Meta:
        model = Product
        fields = [
            "category",
            "city",
            "condition",
            "item_type",
            "price_min",
            "price_max",
            "added_after",
            "seller",
            "seller_type",
            "currency",
            "available",
            "country",
            "administrative_area",
            "locality",
            "delivery_mode",
            "pickup_available",
            "delivery_area",
        ]

    def filter_available(self, queryset, name, value):
        available_products = Q(
            is_suspended=False,
            item_type=Product.ItemType.PRODUCT,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            stock_quantity__gt=0,
        )
        return queryset.filter(available_products if value else ~available_products)

    def filter_city(self, queryset, name, value):
        visible_admin = Q(seller__location_preference__show_admin_area=True) | Q(
            seller__location_preference__isnull=True
        )
        visible_locality = Q(seller__location_preference__show_locality=True)
        return queryset.filter(
            Q(
                seller__public_location__administrative_area__name__icontains=value,
                seller__public_location__is_active=True,
                seller__public_location__precision__in=[
                    "province",
                    "city",
                    "locality",
                    "custom",
                ],
            )
            & visible_admin
            | Q(
                seller__public_location__locality__name__icontains=value,
                seller__public_location__is_active=True,
                seller__public_location__precision__in=["city", "locality"],
            )
            & visible_locality
        ).distinct()

    def filter_public_country(self, queryset, name, value):
        country = Country.objects.filter(
            Q(pk=value) | Q(code__iexact=value) | Q(name__iexact=value),
            is_active=True,
        ).first()
        if country is None:
            return queryset.none()
        visible = Q(seller__location_preference__show_country=True) | Q(
            seller__location_preference__isnull=True
        )
        return (
            queryset.filter(
                seller__public_location__country=country,
                seller__public_location__is_active=True,
            )
            .filter(visible)
            .distinct()
        )

    def filter_public_area(self, queryset, name, value):
        visible = Q(seller__location_preference__show_admin_area=True) | Q(
            seller__location_preference__isnull=True
        )
        return (
            queryset.filter(
                Q(seller__public_location__administrative_area_id=value)
                | Q(seller__public_location__locality_id=value),
                seller__public_location__is_active=True,
                seller__public_location__precision__in=[
                    "province",
                    "city",
                    "locality",
                    "custom",
                ],
            )
            .filter(visible)
            .distinct()
        )

    def filter_public_locality(self, queryset, name, value):
        return queryset.filter(
            seller__public_location__locality_id=value,
            seller__public_location__is_active=True,
            seller__public_location__precision__in=["city", "locality"],
            seller__location_preference__show_locality=True,
        ).distinct()

    def filter_delivery_mode(self, queryset, name, value):
        return queryset.filter(
            seller__delivery_options__mode=value,
            seller__delivery_options__is_active=True,
        ).distinct()

    def filter_pickup_available(self, queryset, name, value):
        pickup_sellers = DeliveryOption.objects.filter(
            mode=DeliveryOption.Mode.PICKUP,
            is_active=True,
        ).values("seller_id")
        return queryset.filter(
            seller_id__in=(
                pickup_sellers
                if value
                else User.objects.exclude(pk__in=pickup_sellers).values("pk")
            )
        )

    def filter_delivery_area(self, queryset, name, value):
        return (
            queryset.filter(
                seller__delivery_options__is_active=True,
            )
            .filter(
                Q(seller__delivery_options__coverage_areas=value)
                | Q(seller__delivery_options__administrative_area_id=value)
                | Q(seller__delivery_options__locality_id=value)
                | Q(seller__delivery_options__mode__in=["national", "international"])
            )
            .distinct()
        )

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        price_min = data.get("price_min")
        price_max = data.get("price_max")
        if price_min is not None and price_max is not None and price_min > price_max:
            raise ValidationError(
                {
                    "price_max": "Le prix maximum doit être supérieur ou égal au prix minimum."
                }
            )
        if (price_min is not None or price_max is not None) and not data.get(
            "currency"
        ):
            raise ValidationError(
                {"currency": "La devise est obligatoire pour filtrer par prix."}
            )
        return super().filter_queryset(queryset)


class ProductOrderingFilter(filters.OrderingFilter):
    allowed_orderings = {
        "price",
        "-price",
        "created_at",
        "-created_at",
        "views_count",
        "-views_count",
        "relevance",
    }

    def filter_queryset(self, request, queryset, view):
        ordering = request.query_params.get(self.ordering_param)
        if ordering == "relevance":
            search = " ".join(request.query_params.get("search", "").split())
            if not search:
                return queryset.order_by("-created_at")
            return queryset.annotate(
                _search_relevance=Case(
                    When(title__icontains=search, then=Value(0)),
                    When(category__name__icontains=search, then=Value(1)),
                    When(description__icontains=search, then=Value(2)),
                    default=Value(3),
                    output_field=IntegerField(),
                )
            ).order_by("_search_relevance", "-created_at")
        if ordering and ordering not in self.allowed_orderings:
            raise ValidationError({self.ordering_param: "Option de tri invalide."})
        return super().filter_queryset(request, queryset, view)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule — la gestion des catégories se fait côté administration."""

    queryset = Category.objects.filter(is_active=True, parent__isnull=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 20


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, ProductOrderingFilter]
    filterset_class = ProductFilter
    pagination_class = ProductPagination
    search_fields = ["title", "description", "category__name"]
    ordering_fields = ["price", "created_at", "views_count"]
    ordering = ["-created_at"]

    def _active_comparison_offers(self, apply_catalog_filters=False):
        queryset = Product.objects.filter(
            item_type=Product.ItemType.PRODUCT,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            is_suspended=False,
            stock_quantity__gt=0,
            price__gte=0,
            seller__is_active=True,
        ).exclude(currency="")
        if not apply_catalog_filters:
            return queryset
        filterset = ProductFilter(
            data=self.request.query_params,
            queryset=queryset,
            request=self.request,
        )
        if filterset.is_valid():
            queryset = filterset.qs
        return filters.SearchFilter().filter_queryset(self.request, queryset, self)

    def _annotate_comparison_summary(self, queryset):
        grouped_offers = (
            self._active_comparison_offers(apply_catalog_filters=True)
            .filter(
                comparison_identity_id=OuterRef("comparison_identity_id"),
                category_id=OuterRef("category_id"),
                currency=OuterRef("currency"),
                condition=OuterRef("condition"),
                comparison_identity__category_id=OuterRef("category_id"),
            )
            .order_by()
            .values("comparison_identity_id")
            .annotate(
                offer_count=Count("pk"),
                seller_count=Count("seller_id", distinct=True),
                lowest_price=Min("price"),
            )
        )
        return queryset.annotate(
            comparison_rank=Window(
                expression=RowNumber(),
                partition_by=[
                    F("comparison_identity_id"),
                    F("currency"),
                    F("condition"),
                    F("status"),
                    F("moderation_status"),
                    F("is_suspended"),
                ],
                order_by=[
                    Case(
                        When(stock_quantity__gt=0, then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    ).asc(),
                    F("price").asc(),
                    F("created_at").desc(),
                ],
            ),
            comparison_offer_count=Case(
                When(
                    comparison_identity__isnull=False,
                    comparison_identity__category_id=F("category_id"),
                    then=Subquery(grouped_offers.values("offer_count")[:1]),
                ),
                default=Value(None),
                output_field=IntegerField(),
            ),
            comparison_seller_count=Case(
                When(
                    comparison_identity__isnull=False,
                    comparison_identity__category_id=F("category_id"),
                    then=Subquery(grouped_offers.values("seller_count")[:1]),
                ),
                default=Value(None),
                output_field=IntegerField(),
            ),
            comparison_lowest_price=Case(
                When(
                    comparison_identity__isnull=False,
                    comparison_identity__category_id=F("category_id"),
                    then=Subquery(grouped_offers.values("lowest_price")[:1]),
                ),
                default=Value(None),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(
            Q(comparison_identity__isnull=True) | Q(comparison_rank=1)
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = Product.objects.select_related(
            "seller",
            "seller__public_location__country",
            "seller__public_location__administrative_area",
            "seller__public_location__locality",
            "seller__location_preference",
            "category",
            "comparison_identity",
        ).prefetch_related("images")
        if self.action == "list":
            queryset = self._annotate_comparison_summary(queryset)
        if self.action in ("list", "retrieve", "comparisons"):
            user = self.request.user
            public_products = Q(
                is_suspended=False,
                status__in=(Product.Status.PUBLISHED, Product.Status.ARCHIVED),
                moderation_status=Product.ModerationStatus.APPROVED,
            )
            if user.is_authenticated:
                return queryset.filter(public_products | Q(seller=user))
            return queryset.filter(public_products)
        return queryset

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_suspended and not (
            request.user.is_authenticated
            and (request.user.is_staff or request.user == instance.seller)
        ):
            raise ValidationError(
                {
                    "detail": "Cette annonce est suspendue et n'est plus accessible au public."
                }
            )
        Product.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        instance.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def toggle_favorite(self, request, pk=None):
        """Raccourci pratique pour le frontend : POST /products/{id}/toggle_favorite/"""
        product = self.get_object()
        favorite, created = Favorite.objects.get_or_create(
            user=request.user, product=product
        )
        if not created:
            favorite.delete()
            Product.objects.filter(pk=product.pk).update(
                favorites_count=F("favorites_count") - 1
            )
            return Response({"favorited": False})
        Product.objects.filter(pk=product.pk).update(
            favorites_count=F("favorites_count") + 1
        )
        return Response({"favorited": True})

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def mine(self, request):
        """Annonces du vendeur connecté, tous statuts confondus — tableau de bord vendeur."""
        queryset = (
            Product.objects.filter(seller=request.user)
            .select_related("category")
            .prefetch_related("images")
        )
        page = self.paginate_queryset(queryset)
        serializer = ProductListSerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def comparisons(self, request, pk=None):
        """Retourne les offres exactes validées et des alternatives distinctes."""
        product = self.get_object()
        reference_words = _significant_words(product.title)
        exact_offers = self._active_comparison_offers().none()
        identity = product.comparison_identity
        summary = {"offer_count": 0, "seller_count": 0, "lowest_price": None}
        if identity and identity.category_id == product.category_id:
            exact_offers = (
                self._active_comparison_offers(apply_catalog_filters=True)
                .filter(
                    comparison_identity=identity,
                    category=product.category,
                    currency=product.currency,
                    condition=product.condition,
                )
                .select_related("seller", "comparison_identity")
                .prefetch_related("images")
                .order_by("price", "-created_at")
            )
            summary_values = exact_offers.aggregate(
                offer_count=Count("pk"),
                seller_count=Count("seller_id", distinct=True),
                lowest_price=Min("price"),
            )
            summary.update(summary_values)

        page = self.paginate_queryset(exact_offers)
        page_data = ProductComparisonSerializer(
            page, many=True, context=self.get_serializer_context()
        ).data
        paginated = self.get_paginated_response(page_data).data
        exact = {
            "identity": (
                {
                    "id": str(identity.pk),
                    "name": identity.name,
                    "brand": identity.brand,
                    "model_name": identity.model_name,
                    "manufacturer_reference": identity.manufacturer_reference,
                    "variant": identity.variant,
                }
                if identity and identity.category_id == product.category_id
                else None
            ),
            "currency": product.currency,
            "offer_count": summary["offer_count"],
            "seller_count": summary["seller_count"],
            "lowest_price": (
                str(summary["lowest_price"])
                if summary["lowest_price"] is not None
                else None
            ),
            "next": paginated["next"],
            "previous": paginated["previous"],
            "results": paginated["results"],
        }

        similar = []
        if reference_words and request.query_params.get("page", "1") == "1":
            title_match = Q()
            for word in reference_words:
                title_match |= Q(title__icontains=word)
            candidates = (
                self._active_comparison_offers()
                .filter(category=product.category, currency=product.currency)
                .filter(title_match)
                .exclude(pk=product.pk)
                .exclude(seller=product.seller)
                .select_related("seller", "category", "comparison_identity")
                .prefetch_related("images")
                .order_by("-created_at")[:100]
            )
            if identity:
                candidates = candidates.exclude(comparison_identity=identity)
            ranked = []
            for candidate in candidates:
                candidate_words = _significant_words(candidate.title)
                overlap = len(reference_words & candidate_words)
                union_size = len(reference_words | candidate_words)
                if overlap >= 2 and union_size and overlap / union_size >= 0.35:
                    ranked.append((overlap / union_size, candidate))
            ranked.sort(key=lambda item: (-item[0], item[1].price))
            similar = ProductListSerializer(
                [candidate for _, candidate in ranked[:5]],
                many=True,
                context=self.get_serializer_context(),
            ).data

        return Response({"exact": exact, "similar": similar})


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("product")


class SellerFavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = SellerFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return SellerFavorite.objects.filter(user=self.request.user).select_related(
            "seller"
        )


class SavedSearchViewSet(viewsets.ModelViewSet):
    serializer_class = SavedSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user)
