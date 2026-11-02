"""
URLs de l'app `reviews`, montées sous `/api/v1/reviews/` (voir config/urls.py).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "reviews"

router = DefaultRouter()
router.register("reviews", views.ReviewViewSet, basename="review")

urlpatterns = [
    path("", include(router.urls)),
]

# GET  /reviews/?user=<username>       avis reçus par un utilisateur
# GET  /reviews/?product=<id>          avis liés à un produit précis
# POST /reviews/                       laisser un avis (commande livrée requise)
