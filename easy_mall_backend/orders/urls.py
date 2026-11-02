"""
URLs de l'app `orders`, montées sous `/api/v1/orders/` (voir config/urls.py).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "orders"

router = DefaultRouter()
router.register("orders", views.OrderViewSet, basename="order")
router.register("my-sales", views.SellerSalesViewSet, basename="seller-sales")

urlpatterns = [
    path("", include(router.urls)),
]

# Routes générées automatiquement, pour référence :
#   GET/POST   /orders/            (POST = checkout, via OrderCreateSerializer)
#   GET/DELETE /orders/{id}/       (DELETE masque une commande terminale pour l'acheteur)
#   POST       /orders/{id}/cancel/
#   GET/DELETE /my-sales/{id}/     (DELETE masque une vente terminale pour le vendeur)