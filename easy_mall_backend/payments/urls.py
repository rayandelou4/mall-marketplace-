"""
URLs de l'app `payments`, montées sous `/api/v1/payments/` (voir config/urls.py).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "payments"

router = DefaultRouter()
router.register("markets", views.SupportedMarketViewSet, basename="market")
router.register("providers", views.PaymentProviderViewSet, basename="provider")

urlpatterns = [
    path("", include(router.urls)),
    path("config/", views.PaymentConfigView.as_view(), name="config"),
    path("history/", views.PaymentListView.as_view(), name="history"),
    path("initiate/", views.PaymentInitiateView.as_view(), name="initiate"),
    path("webhook/confirm/", views.PaymentConfirmView.as_view(), name="webhook-confirm"),
]