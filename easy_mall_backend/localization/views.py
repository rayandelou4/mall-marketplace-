from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AdministrativeArea,
    Country,
    DeliveryOption,
    PickupLocation,
    PrivateAddress,
    SellerLocationPreference,
    SellerPublicLocation,
)
from .serializers import (
    AdministrativeAreaSerializer,
    CountrySerializer,
    DeliveryOptionSerializer,
    PickupLocationSerializer,
    PrivateAddressSerializer,
    SellerLocationPreferenceSerializer,
    SellerPublicLocationSerializer,
)

User = get_user_model()


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
    permission_classes = [permissions.AllowAny]


class AdministrativeAreaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdministrativeAreaSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = AdministrativeArea.objects.filter(is_active=True).select_related(
            "country", "parent"
        )
        country_id = self.request.query_params.get("country")
        parent_id = self.request.query_params.get("parent")
        level = self.request.query_params.get("level")
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if level:
            queryset = queryset.filter(level=level)
        search = self.request.query_params.get("search", "").strip()[:100]
        if search:
            matches = [
                area.pk
                for area in queryset
                if search.casefold() in area.name.casefold()
                or search.casefold() in area.slug.casefold()
                or any(search.casefold() in name.casefold() for name in area.alt_names)
            ]
            queryset = queryset.filter(pk__in=matches)
        return queryset


class PrivateAddressViewSet(viewsets.ModelViewSet):
    serializer_class = PrivateAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PrivateAddress.objects.filter(user=self.request.user).select_related(
            "country", "administrative_area", "locality"
        )

    def perform_create(self, serializer):
        serializer.save()


class SellerPublicLocationView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username=None):
        if username in {None, "me"}:
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentification requise."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            user = request.user
        else:
            user = get_object_or_404(User, username=username, is_active=True)
        location = (
            SellerPublicLocation.objects.filter(user=user, is_active=True)
            .select_related("country", "administrative_area", "locality")
            .first()
        )
        if not location:
            return Response(
                {"detail": "Aucune localisation publique configurée."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SellerPublicLocationSerializer(location)
        return Response(serializer.data)

    def _save_location(self, request, username, partial):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if username and username != request.user.username:
            return Response(
                {"detail": "Vous ne pouvez modifier que votre propre localisation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        location = SellerPublicLocation.objects.filter(user=request.user).first()
        serializer = SellerPublicLocationSerializer(
            location, data=request.data, partial=False
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)

    def put(self, request, username=None):
        return self._save_location(request, username, partial=False)

    def patch(self, request, username=None):
        return self._save_location(request, username, partial=True)


class SellerLocationPreferenceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        preference, _ = SellerLocationPreference.objects.get_or_create(
            seller=request.user
        )
        return Response(SellerLocationPreferenceSerializer(preference).data)

    def patch(self, request):
        preference, _ = SellerLocationPreference.objects.get_or_create(
            seller=request.user
        )
        serializer = SellerLocationPreferenceSerializer(
            preference, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PickupLocationViewSet(viewsets.ModelViewSet):
    serializer_class = PickupLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PickupLocation.objects.filter(seller=self.request.user).select_related(
            "country", "administrative_area", "locality"
        )

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class DeliveryOptionViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryOptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            DeliveryOption.objects.filter(seller=self.request.user)
            .select_related("country", "administrative_area", "locality")
            .prefetch_related("coverage_areas")
        )

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def toggle_active(self, request, pk=None):
        option = self.get_object()
        option.is_active = not option.is_active
        option.save(update_fields=["is_active"])
        return Response(DeliveryOptionSerializer(option).data)
