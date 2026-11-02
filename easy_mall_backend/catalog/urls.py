"""
URLs de l'app `catalog`, montées sous `/api/v1/catalog/` (voir config/urls.py).

Le DefaultRouter génère automatiquement les routes standards pour chaque
ViewSet (list/create/retrieve/update/destroy) ainsi que les @action
personnalisées (ex. `toggle_favorite` sur ProductViewSet).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "catalog"

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("products", views.ProductViewSet, basename="product")
router.register("favorites", views.FavoriteViewSet, basename="favorite")
router.register("seller-favorites", views.SellerFavoriteViewSet, basename="seller-favorite")
router.register("saved-searches", views.SavedSearchViewSet, basename="saved-search")

urlpatterns = [
    path("", include(router.urls)),
]

# Routes générées automatiquement, pour référence :
#   GET/POST      /categories/
#   GET           /categories/{id}/
#   GET/POST      /products/
#   GET/PUT/PATCH/DELETE /products/{id}/
#   POST          /products/{id}/toggle_favorite/
#   GET/POST      /favorites/
#   DELETE        /favorites/{id}/
#   GET/POST      /seller-favorites/
#   DELETE        /seller-favorites/{id}/
#   GET/POST/PUT/PATCH/DELETE /saved-searches/