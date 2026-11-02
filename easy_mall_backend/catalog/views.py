"""
Vues de l'app `catalog`.

Nécessite `pip install django-filter` et `django_filters` dans
INSTALLED_APPS pour les filtres du catalogue (catégorie, ville, état,
prix, date d'ajout — cahier des charges §"Catalogue").
"""

import re

import django_filters
from django.db.models import Case, F, IntegerField, Q, Value, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import User
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
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "pour",
    "avec", "sur", "dans", "au", "aux", "ce", "cette", "ces", "à",
}


def _significant_words(title):
    """Mots de 3+ lettres/chiffres, hors mots vides — base du rapprochement."""
    words = re.findall(r"[a-zàâäéèêëïîôöùûüç0-9]+", title.lower())
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

    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte", min_value=0)
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte", min_value=0)
    added_after = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    city = django_filters.CharFilter(method="filter_city")
    seller = django_filters.CharFilter(field_name="seller__username")
    seller_type = django_filters.ChoiceFilter(
        field_name="seller__seller_type", choices=User.SellerType.choices
    )
    condition = django_filters.ChoiceFilter(choices=Product.Condition.choices)
    item_type = django_filters.ChoiceFilter(choices=Product.ItemType.choices)
    currency = django_filters.CharFilter(field_name="currency", lookup_expr="iexact", max_length=3)
    available = django_filters.BooleanFilter(method="filter_available")

    class Meta:
        model = Product
        fields = [
            "category", "city", "condition", "item_type", "price_min", "price_max",
            "added_after", "seller", "seller_type", "currency", "available",
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
        return queryset.filter(Q(city__icontains=value) | Q(seller__city__icontains=value))

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        price_min = data.get("price_min")
        price_max = data.get("price_max")
        if price_min is not None and price_max is not None and price_min > price_max:
            raise ValidationError({"price_max": "Le prix maximum doit être supérieur ou égal au prix minimum."})
        if (price_min is not None or price_max is not None) and not data.get("currency"):
            raise ValidationError({"currency": "La devise est obligatoire pour filtrer par prix."})
        return super().filter_queryset(queryset)


class ProductOrderingFilter(filters.OrderingFilter):
    allowed_orderings = {"price", "-price", "created_at", "-created_at", "relevance"}

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


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, ProductOrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["title", "description", "category__name"]
    ordering_fields = ["price", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Product.objects.select_related("seller", "category").prefetch_related("images")
        if self.action in ("list", "retrieve"):
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
        if instance.is_suspended and not (request.user.is_authenticated and (request.user.is_staff or request.user == instance.seller)):
            raise ValidationError({"detail": "Cette annonce est suspendue et n'est plus accessible au public."})
        Product.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        instance.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def toggle_favorite(self, request, pk=None):
        """Raccourci pratique pour le frontend : POST /products/{id}/toggle_favorite/"""
        product = self.get_object()
        favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            favorite.delete()
            Product.objects.filter(pk=product.pk).update(favorites_count=F("favorites_count") - 1)
            return Response({"favorited": False})
        Product.objects.filter(pk=product.pk).update(favorites_count=F("favorites_count") + 1)
        return Response({"favorited": True})

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        """Annonces du vendeur connecté, tous statuts confondus — tableau de bord vendeur."""
        queryset = Product.objects.filter(seller=request.user).select_related("category").prefetch_related("images")
        page = self.paginate_queryset(queryset)
        serializer = ProductListSerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def comparisons(self, request, pk=None):
        """
        Le "comparateur de prix" du cahier des charges : offres équivalentes
        chez d'autres vendeurs (même catégorie + chevauchement de mots
        significatifs du titre). Le rapprochement se fait en Python plutôt
        qu'avec une extension de recherche spécifique à Postgres (ex.
        pg_trgm), pour fonctionner identiquement avec SQLite en dev.

        Note de perf : charge les candidats de la catégorie en mémoire pour
        les noter un par un — largement suffisant à ce volume, mais à
        reconsidérer (recherche plein texte côté DB) si le catalogue devient
        très grand.
        """
        product = self.get_object()
        reference_words = _significant_words(product.title)

        candidates = (
            Product.objects.filter(
                category=product.category,
                status=Product.Status.PUBLISHED,
                moderation_status=Product.ModerationStatus.APPROVED,
            )
            .exclude(seller=product.seller)
            .exclude(pk=product.pk)
            .select_related("seller")
            .prefetch_related("images")
        )

        scored = []
        for candidate in candidates:
            overlap = len(reference_words & _significant_words(candidate.title))
            if overlap > 0 or not reference_words:
                scored.append((overlap, candidate))
        scored.sort(key=lambda pair: (-pair[0], pair[1].price))

        results = [candidate for _, candidate in scored[:10]]
        serializer = ProductComparisonSerializer(
            results, many=True, context={"reference_city": product.city}
        )
        return Response(serializer.data)


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
        return SellerFavorite.objects.filter(user=self.request.user).select_related("seller")


class SavedSearchViewSet(viewsets.ModelViewSet):
    serializer_class = SavedSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user)
