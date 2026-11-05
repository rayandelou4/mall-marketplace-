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
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )

    class Meta:
        model = AdministrativeArea
        fields = [
            "id",
            "country",
            "country_name",
            "parent",
            "parent_name",
            "level",
            "name",
            "slug",
            "alt_names",
            "is_active",
        ]


class SellerPublicLocationSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    administrative_area_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    administrative_area_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=150
    )
    locality_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = SellerPublicLocation
        fields = [
            "id",
            "country",
            "country_id",
            "administrative_area",
            "administrative_area_id",
            "administrative_area_name",
            "locality",
            "locality_id",
            "precision",
            "public_note",
            "display_name",
            "is_active",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        preference = getattr(instance.user, "location_preference", None)
        show_country = preference is None or preference.show_country
        show_admin_area = preference is None or preference.show_admin_area
        show_locality = (
            preference is not None
            and preference.show_locality
            and instance.precision
            in {instance.Precision.CITY, instance.Precision.LOCALITY}
            and (
                instance.locality is None
                or instance.locality.level != AdministrativeArea.LEVEL_NEIGHBORHOOD
                or instance.precision == instance.Precision.LOCALITY
            )
        )
        if not show_country:
            data["country"] = None
        if not show_admin_area or instance.precision == instance.Precision.COUNTRY:
            data["administrative_area"] = None
        if not show_locality:
            data["locality"] = None
        if preference is None or not preference.show_public_note:
            data["public_note"] = ""
        return data

    def validate(self, attrs):
        country_id = attrs.get("country_id", getattr(self.instance, "country_id", None))
        admin_id = attrs.get(
            "administrative_area_id",
            getattr(self.instance, "administrative_area_id", None),
        )
        locality_id = attrs.get(
            "locality_id", getattr(self.instance, "locality_id", None)
        )
        country = (
            Country.objects.filter(pk=country_id, is_active=True).first()
            if country_id
            else None
        )
        if not country:
            raise serializers.ValidationError(
                {"country_id": "Pays introuvable ou inactif."}
            )
        administrative_area = (
            AdministrativeArea.objects.filter(pk=admin_id, is_active=True).first()
            if admin_id
            else None
        )
        if admin_id and not administrative_area:
            raise serializers.ValidationError(
                {"administrative_area_id": "Subdivision introuvable ou inactive."}
            )
        locality = (
            AdministrativeArea.objects.filter(pk=locality_id, is_active=True).first()
            if locality_id
            else None
        )
        if locality_id and not locality:
            raise serializers.ValidationError(
                {"locality_id": "Localité introuvable ou inactive."}
            )
        if (
            country
            and administrative_area
            and administrative_area.country_id != country.pk
        ):
            raise serializers.ValidationError(
                {
                    "administrative_area_id": "La subdivision doit appartenir au pays sélectionné."
                }
            )
        if country and locality and locality.country_id != country.pk:
            raise serializers.ValidationError(
                {"locality_id": "La localité doit appartenir au pays sélectionné."}
            )
        if (
            locality
            and administrative_area
            and locality.parent_id != administrative_area.pk
        ):
            raise serializers.ValidationError(
                {
                    "locality_id": "La localité n'appartient pas à la subdivision choisie."
                }
            )
        return attrs

    def _save_with_area_name(self, attrs, instance=None):
        area_name = attrs.pop("administrative_area_name", "").strip()
        area_id = attrs.get(
            "administrative_area_id",
            getattr(instance, "administrative_area_id", None),
        )
        country_id = attrs.get("country_id", getattr(instance, "country_id", None))
        if area_name and not area_id:
            area, _ = AdministrativeArea.objects.get_or_create(
                country_id=country_id,
                parent=None,
                level=AdministrativeArea.LEVEL_PROVINCE,
                name=area_name,
            )
            attrs["administrative_area_id"] = area.pk
        return attrs

    def create(self, validated_data):
        return super().create(self._save_with_area_name(validated_data))

    def update(self, instance, validated_data):
        return super().update(
            instance, self._save_with_area_name(validated_data, instance)
        )


class PrivateAddressSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    administrative_area_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    locality_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    country_code = serializers.CharField(write_only=True, required=False, max_length=3)
    country_name = serializers.CharField(write_only=True, required=False, max_length=150)
    administrative_area_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=150
    )

    class Meta:
        model = PrivateAddress
        fields = [
            "id",
            "label",
            "country",
            "country_id",
            "country_code",
            "country_name",
            "administrative_area",
            "administrative_area_id",
            "administrative_area_name",
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
        country_id = attrs.get("country_id", getattr(self.instance, "country_id", None))
        country_code = attrs.get("country_code", "").strip().upper()
        admin_id = attrs.get(
            "administrative_area_id",
            getattr(self.instance, "administrative_area_id", None),
        )
        locality_id = attrs.get(
            "locality_id", getattr(self.instance, "locality_id", None)
        )
        country = (
            Country.objects.filter(pk=country_id, is_active=True).first()
            if country_id
            else None
        )
        if not country and country_code:
            country = Country.objects.filter(code=country_code, is_active=True).first()
        if not country and not (country_code and attrs.get("country_name", "").strip()):
            raise serializers.ValidationError(
                {"country_id": "Le pays est obligatoire."}
            )
        if country_id and not country:
            raise serializers.ValidationError(
                {"country_id": "Pays introuvable ou inactif."}
            )
        administrative_area = (
            AdministrativeArea.objects.filter(pk=admin_id, is_active=True).first()
            if admin_id
            else None
        )
        if admin_id and not administrative_area:
            raise serializers.ValidationError(
                {"administrative_area_id": "Subdivision introuvable ou inactive."}
            )
        locality = (
            AdministrativeArea.objects.filter(pk=locality_id, is_active=True).first()
            if locality_id
            else None
        )
        if locality_id and not locality:
            raise serializers.ValidationError(
                {"locality_id": "Localité introuvable ou inactive."}
            )
        if administrative_area and country and administrative_area.country_id != country.pk:
            raise serializers.ValidationError(
                {"administrative_area_id": "La subdivision ne correspond pas au pays."}
            )
        if locality and country and locality.country_id != country.pk:
            raise serializers.ValidationError(
                {"locality_id": "La localité ne correspond pas au pays."}
            )
        if (
            locality
            and administrative_area
            and locality.parent_id != administrative_area.pk
        ):
            raise serializers.ValidationError(
                {"locality_id": "La localité doit appartenir à la subdivision choisie."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        country_id = validated_data.pop("country_id", None)
        country_code = validated_data.pop("country_code", "").strip().upper()
        country_name = validated_data.pop("country_name", "").strip()
        country = Country.objects.filter(pk=country_id).first() if country_id else None
        if country is None:
            country, _ = Country.objects.get_or_create(
                code=country_code,
                defaults={"name": country_name},
            )

        area_id = validated_data.pop("administrative_area_id", None)
        area_name = validated_data.pop("administrative_area_name", "").strip()
        administrative_area = (
            AdministrativeArea.objects.filter(pk=area_id).first() if area_id else None
        )
        if administrative_area is None and area_name:
            administrative_area, _ = AdministrativeArea.objects.get_or_create(
                country=country,
                parent=None,
                level=AdministrativeArea.LEVEL_PROVINCE,
                name=area_name,
            )

        locality_id = validated_data.pop("locality_id", None)
        instance = PrivateAddress(
            user=request.user,
            country=country,
            administrative_area=administrative_area,
            locality_id=locality_id,
            **validated_data,
        )
        instance.save()
        return instance


class PickupLocationSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    country_id = serializers.UUIDField(write_only=True)
    administrative_area_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    locality_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

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
            "country_id",
            "administrative_area_id",
            "locality_id",
        ]

    def validate(self, attrs):
        country_id = attrs.get("country_id", getattr(self.instance, "country_id", None))
        admin_id = attrs.get(
            "administrative_area_id",
            getattr(self.instance, "administrative_area_id", None),
        )
        locality_id = attrs.get(
            "locality_id", getattr(self.instance, "locality_id", None)
        )
        if not Country.objects.filter(pk=country_id, is_active=True).exists():
            raise serializers.ValidationError(
                {"country_id": "Pays introuvable ou inactif."}
            )
        areas = {}
        for field, area_id in (
            ("administrative_area_id", admin_id),
            ("locality_id", locality_id),
        ):
            area = (
                AdministrativeArea.objects.filter(pk=area_id, is_active=True).first()
                if area_id
                else None
            )
            if area_id and (not area or str(area.country_id) != str(country_id)):
                raise serializers.ValidationError(
                    {field: "Cette zone ne correspond pas au pays sélectionné."}
                )
            areas[field] = area
        admin_area = areas["administrative_area_id"]
        locality = areas["locality_id"]
        if admin_area and locality and locality.parent_id != admin_area.pk:
            raise serializers.ValidationError(
                {
                    "locality_id": "La localité n'appartient pas à la subdivision choisie."
                }
            )
        return attrs


class DeliveryOptionSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    administrative_area = AdministrativeAreaSerializer(read_only=True)
    locality = AdministrativeAreaSerializer(read_only=True)
    coverage_areas = AdministrativeAreaSerializer(many=True, read_only=True)
    country_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    administrative_area_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    locality_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    coverage_area_ids = serializers.PrimaryKeyRelatedField(
        source="coverage_areas",
        queryset=AdministrativeArea.objects.filter(is_active=True),
        many=True,
        write_only=True,
        required=False,
    )

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
            "country_id",
            "administrative_area_id",
            "locality_id",
            "coverage_area_ids",
        ]
        read_only_fields = ["seller"]

    def validate(self, attrs):
        country_id = attrs.get("country_id", getattr(self.instance, "country_id", None))
        area_ids = [
            attrs.get(
                "administrative_area_id",
                getattr(self.instance, "administrative_area_id", None),
            ),
            attrs.get("locality_id", getattr(self.instance, "locality_id", None)),
        ]
        country = (
            Country.objects.filter(pk=country_id, is_active=True).first()
            if country_id
            else None
        )
        if country_id and not country:
            raise serializers.ValidationError(
                {"country_id": "Pays introuvable ou inactif."}
            )
        areas = list(
            AdministrativeArea.objects.filter(
                pk__in=[value for value in area_ids if value]
            )
        )
        if country and any(area.country_id != country.pk for area in areas):
            raise serializers.ValidationError(
                "Les zones doivent appartenir au pays sélectionné."
            )
        for field, area_id in zip(("administrative_area_id", "locality_id"), area_ids):
            if area_id and not any(str(area.pk) == str(area_id) for area in areas):
                raise serializers.ValidationError(
                    {field: "Zone introuvable ou inactive."}
                )
        coverage_areas = attrs.get("coverage_areas", [])
        if country and any(area.country_id != country.pk for area in coverage_areas):
            raise serializers.ValidationError(
                {
                    "coverage_area_ids": "Toutes les zones desservies doivent appartenir au pays sélectionné."
                }
            )
        return attrs


class SellerLocationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerLocationPreference
        fields = [
            "id",
            "show_country",
            "show_admin_area",
            "show_locality",
            "show_public_note",
            "updated_at",
        ]


class SellerPublicLocationFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerPublicLocation
        fields = [
            "country",
            "administrative_area",
            "locality",
            "precision",
            "public_note",
            "is_active",
        ]
