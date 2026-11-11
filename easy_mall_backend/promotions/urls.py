from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CheckoutQuoteView, LoyaltyStatusView, SellerPromotionViewSet

app_name = "promotions"
router = DefaultRouter()
router.register("mine", SellerPromotionViewSet, basename="seller-promotion")

urlpatterns = [
    path("", include(router.urls)),
    path("checkout-quote/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("loyalty/me/", LoyaltyStatusView.as_view(), name="loyalty-status"),
]