from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User

from .models import (
    AdministrativeArea,
    Country,
    DeliveryOption,
    PickupLocation,
    PrivateAddress,
    SellerLocationPreference,
    SellerPublicLocation,
)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "code", "name", "local_name", "phone_code", "is_active"]


class AdministrativeAreaSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, allow_null=True)

    class Meta:
        model = AdministrativeArea
        fields = ["id", "country", "country_name", "parent", "parent_name", "level", "name", "slug", "alt_names", "is_active"]


class SellerPublicLocationSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    administrative_area_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    locality_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = SellerPublicLocation
        fields = [
            "id",
            "country",
            "country_id",
            "administrative_area",
            "administrative_area_id",
            "locality",
            "locality_id",
            "precision",
            "public_note",
            "display_name",
            "is_active",
        ]

    def validate(self, attrs):
        country_id = attrs.get("country_id") or getattr(self.instance, "country_id", None)
        admin_id = attrs.get("administrative_area_id")
        locality_id = attrs.get("locality_id")
        country = Country.objects.filter(pk=country_id).first() if country_id else getattr(self.instance, "country", None)
        administrative_area = None
        locality = None
        if admin_id:
            administrative_area = AdministrativeArea.objects.filter(pk=admin_id).first()
        if locality_id:
            locality = AdministrativeArea.objects.filter(pk=locality_id).first()
        if country and administrative_area and administrative_area.country_id != country.pk:
            raise serializers.ValidationError({"administrative_area_id": "La subdivision doit appartenir au pays sélectionné."})
        if country and locality and locality.country_id != country.pk:
            raise serializers.ValidationError({"locality_id": "La localité doit appartenir au pays sélectionné."})
        if locality and administrative_area and locality.parent_id not in {administrative_area.pk, None}:
            raise serializers.ValidationError({"locality_id": "La localité n'appartient pas à la subdivision choisie."})
        return attrs

    def create(self, validated_data):
        validated_data["country_id"] = validated_data.pop("country_id", validated_data.get("country_id"))
        valid_country = validated_data.pop("country_id", None)
        admin_id = validated_data.pop("administrative_area_id", None)
        locality_id = validated_data.pop("locality_id", None)
        if valid_country:
            validated_data["country_id"] = valid_country
        if admin_id is not None:
            validated_data["administrative_area_id"] = admin_id
        if locality_id is not None:
            validated_data["locality_id"] = locality_id
        return super().create(validated_data)


class PrivateAddressSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    administrative_area_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    locality_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PrivateAddress
        fields = [
            "id",
            "label",
            "country",
            "country_id",
            "administrative_area",
            "administrative_area_id",
            "locality",
            "locality_id",
            "street_address",
            "landmark",
            "phone_number",
            "is_default",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        country_id = attrs.get("country_id") or getattr(self.instance, "country_id", None)
        admin_id = attrs.get("administrative_area_id")
        locality_id = attrs.get("locality_id")
        if not country_id:
            raise serializers.ValidationError({"country_id": "Le pays est obligatoire."})
        country = Country.objects.filter(pk=country_id).first()
        if not country:
            raise serializers.ValidationError({"country_id": "Pays introuvable."})
        administrative_area = None
        locality = None
        if admin_id:
            administrative_area = AdministrativeArea.objects.filter(pk=admin_id).first()
            if not administrative_area:
                raise serializers.ValidationError({"administrative_area_id": "Subdivision introuvable."})
        if locality_id:
            locality = AdministrativeArea.objects.filter(pk=locality_id).first()
            if not locality:
                raise serializers.ValidationError({"locality_id": "Localité introuvable."})
        if administrative_area and administrative_area.country_id != country.pk:
            raise serializers.ValidationError({"administrative_area_id": "La subdivision ne correspond pas au pays."})
        if locality and locality.country_id != country.pk:
            raise serializers.ValidationError({"locality_id": "La localité ne correspond pas au pays."})
        if locality and administrative_area and locality.parent_id not in {administrative_area.pk, None}:
            raise serializers.ValidationError({"locality_id": "La localité doit appartenir à la subdivision choisie."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        validated_data["country_id"] = validated_data.pop("country_id")
        if "administrative_area_id" in validated_data:
            validated_data["administrative_area_id"] = validated_data.pop("administrative_area_id")
        if "locality_id" in validated_data:
            validated_data["locality_id"] = validated_data.pop("locality_id")
        instance = PrivateAddress.objects.create(**validated_data)
        instance.full_clean()
        return instance


class PickupLocationSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)

    class Meta:
        model = PickupLocation
        fields = [
            "id",
            "name",
            "location_type",
            "country",
            "administrative_area",
            "locality",
            "description",
            "instructions",
            "is_active",
        ]


class DeliveryOptionSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    coverage_areas = AdministrativeAreaSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryOption
        fields = [
            "id",
            "seller",
            "mode",
            "country",
            "administrative_area",
            "locality",
            "coverage_areas",
            "conditions",
            "fees",
            "estimated_delivery_days",
            "is_active",
        ]
        read_only_fields = ["seller"]


class SellerLocationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerLocationPreference
        fields = ["id", "show_country", "show_admin_area", "show_locality", "show_public_note", "updated_at"]


class SellerPublicLocationFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerPublicLocation
        fields = ["country", "administrative_area", "locality", "precision", "public_note", "is_active"]
