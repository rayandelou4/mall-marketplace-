import uuid

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from catalog.models import Product
from catalog.serializers import ProductListSerializer

from . import services
from .serializers import VisualSearchRequestSerializer


class VisualSearchConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"enabled": services.is_configured()})


class VisualSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "visual_search"

    def post(self, request):
        if not services.is_configured():
            return Response(
                {"detail": "La recherche visuelle n’est pas configurée."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = VisualSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        image.seek(0)
        result_ids = services.get_provider().search(
            image=image,
            filters=serializer.validated_data.get("filters", {}),
        )
        if not isinstance(result_ids, (list, tuple)):
            return Response(
                {"detail": "Le moteur a retourné un résultat invalide."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ordered_ids = []
        for result_id in result_ids[:50]:
            try:
                product_id = uuid.UUID(str(result_id))
            except (TypeError, ValueError, AttributeError):
                continue
            if product_id not in ordered_ids:
                ordered_ids.append(product_id)
        if not ordered_ids:
            return Response({"results": []})

        products = Product.objects.filter(
            pk__in=ordered_ids,
            item_type=Product.ItemType.PRODUCT,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            is_suspended=False,
            stock_quantity__gt=0,
            seller__is_active=True,
        ).select_related(
            "seller", "category", "comparison_identity", "seller__public_location",
            "seller__location_preference",
        ).prefetch_related("images", "variants")
        products_by_id = {product.pk: product for product in products}
        ordered_products = [products_by_id[pk] for pk in ordered_ids if pk in products_by_id]
        return Response({
            "results": ProductListSerializer(
                ordered_products, many=True, context={"request": request}
            ).data
        })