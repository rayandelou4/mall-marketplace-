from django.db.models import Sum
from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.serializers import OrderCreateSerializer

from .models import LoyaltyTransaction, Promotion
from .serializers import PromotionSerializer
from .services import get_loyalty_program, get_points_balance


class SellerPromotionViewSet(viewsets.ModelViewSet):
    serializer_class = PromotionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Promotion.objects.filter(seller=self.request.user).prefetch_related("products")

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class CheckoutQuoteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(
            data=request.data,
            context={"request": request, "quote_only": True},
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.get_quote())


class LoyaltyStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        program = get_loyalty_program()
        recent = LoyaltyTransaction.objects.filter(user=request.user).order_by("-created_at")[:10]
        return Response({
            "is_active": program.is_active,
            "points_balance": get_points_balance(request.user),
            "points_per_currency_unit": program.points_per_currency_unit,
            "redemption_value_per_point": program.redemption_value_per_point,
            "max_redemption_percent": program.max_redemption_percent,
            "currency_rules": program.currency_rules,
            "recent_transactions": [
                {"kind": item.kind, "points_delta": item.points_delta, "created_at": item.created_at}
                for item in recent
            ],
        })