import uuid
from decimal import Decimal

from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from catalog.models import Category, Product
from catalog.serializers import ProductListSerializer

from . import services
from .serializers import AssistantQuerySerializer, BuyerCriteriaSerializer


class BuyerAssistantConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"enabled": services.is_configured()})


class BuyerAssistantSearchView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "buyer_assistant"

    def post(self, request):
        if not services.is_configured():
            return Response(
                {"detail": "L’assistant acheteur n’est pas configuré."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        query_serializer = AssistantQuerySerializer(data=request.data)
        query_serializer.is_valid(raise_exception=True)
        message = query_serializer.validated_data["message"]
        categories = list(
            Category.objects.filter(is_active=True)
            .order_by("order", "name")
            .values("id", "name", "parent_id")
        )
        provider = services.get_provider()
        criteria_serializer = BuyerCriteriaSerializer(
            data=provider.understand_needs(message=message, categories=categories)
        )
        criteria_serializer.is_valid(raise_exception=True)
        criteria = criteria_serializer.validated_data

        candidates = Product.objects.filter(
            item_type=Product.ItemType.PRODUCT,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            is_suspended=False,
            stock_quantity__gt=0,
            seller__is_active=True,
            seller__is_suspended=False,
        )
        if criteria.get("max_price") is not None:
            candidates = candidates.filter(
                price__lte=criteria["max_price"], currency=criteria["currency"]
            )
        if criteria.get("category_id"):
            candidates = candidates.filter(category_id=criteria["category_id"])
        if criteria.get("condition"):
            candidates = candidates.filter(condition=criteria["condition"])
        keyword_query = Q()
        for keyword in criteria.get("keywords", []):
            normalized = keyword.strip()
            if normalized:
                keyword_query |= (
                    Q(title__icontains=normalized)
                    | Q(description__icontains=normalized)
                    | Q(category__name__icontains=normalized)
                )
        if keyword_query:
            candidates = candidates.filter(keyword_query)

        candidate_products = list(
            candidates.select_related("seller", "category", "comparison_identity")
            .prefetch_related("images", "variants")
            .order_by("-views_count", "-created_at")[:100]
        )
        if not candidate_products:
            return Response({"criteria": criteria_serializer.data, "offers": []})

        serialized = ProductListSerializer(
            candidate_products, many=True, context={"request": request}
        ).data
        candidate_by_id = {str(item["id"]): item for item in serialized}
        ranking = provider.rank_candidates(
            message=message,
            criteria=criteria_serializer.data,
            candidates=[
                {
                    "id": item["id"],
                    "title": item["title"],
                    "description": product.description,
                    "price": item["price"],
                    "currency": item["currency"],
                    "condition": item["condition_display"],
                    "category": item["category_name"],
                    "seller_rating": item["seller_rating"],
                    "city": item["city"],
                    "stock_quantity": item["stock_quantity"],
                    "comparison_identity": item["comparison_identity"],
                }
                for product, item in zip(candidate_products, serialized)
            ],
        )
        if not isinstance(ranking, (list, tuple)):
            return Response(
                {"detail": "L’assistant a retourné un classement invalide."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ordered_ids = []
        for value in ranking:
            candidate_id = value.get("product_id") if isinstance(value, dict) else value
            try:
                candidate_id = str(uuid.UUID(str(candidate_id)))
            except (TypeError, ValueError, AttributeError):
                continue
            if candidate_id in candidate_by_id and candidate_id not in ordered_ids:
                ordered_ids.append(candidate_id)
            if len(ordered_ids) >= 12:
                break

        cheapest_by_currency = {}
        for product_id in ordered_ids:
            item = candidate_by_id[product_id]
            price = Decimal(str(item["price"]))
            currency = item["currency"]
            cheapest_by_currency[currency] = min(
                cheapest_by_currency.get(currency, price), price
            )
        offers = []
        for product_id in ordered_ids:
            item = candidate_by_id[product_id]
            features = []
            identity = item.get("comparison_identity") or {}
            for key, label in (("brand", "Marque"), ("model_name", "Modèle"), ("variant", "Variante")):
                if identity.get(key):
                    features.append(f"{label} : {identity[key]}")
            if criteria.get("max_price") is not None:
                features.append("Dans le budget indiqué")
            if Decimal(str(item["price"])) == cheapest_by_currency[item["currency"]]:
                features.append(f"Parmi les prix les plus bas en {item['currency']}")
            offers.append({"product": item, "reasons": features})

        return Response({"criteria": criteria_serializer.data, "offers": offers})