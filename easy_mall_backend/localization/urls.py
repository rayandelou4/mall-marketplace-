from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "localization"

router = DefaultRouter()
router.register("countries", views.CountryViewSet, basename="country")
router.register("areas", views.AdministrativeAreaViewSet, basename="area")
router.register("addresses", views.PrivateAddressViewSet, basename="address")
router.register("pickup-locations", views.PickupLocationViewSet, basename="pickup-location")
router.register("delivery-options", views.DeliveryOptionViewSet, basename="delivery-option")

urlpatterns = [
    path("", include(router.urls)),
    path("seller-location/<slug:username>/", views.SellerPublicLocationView.as_view(), name="seller-location-detail"),
    path("seller-location/me/", views.SellerPublicLocationView.as_view(), name="seller-location-me"),
    path("seller-location/preferences/", views.SellerLocationPreferenceView.as_view(), name="seller-location-preferences"),
]
