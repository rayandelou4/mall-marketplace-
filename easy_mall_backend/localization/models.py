import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Country(models.Model):
    """Pays supporté par la marketplace. L'objectif est de supporter plusieurs pays sans durcir des listes en frontend."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=3, unique=True, help_text="Code ISO alpha-3, ex. COD pour la RDC"
    )
    name = models.CharField(max_length=150, unique=True)
    local_name = models.CharField(max_length=150, blank=True)
    phone_code = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "countries"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AdministrativeArea(models.Model):
    """Hiérarchie administrative générique : province -> ville -> quartier."""

    LEVEL_COUNTRY = "country"
    LEVEL_PROVINCE = "province"
    LEVEL_CITY = "city"
    LEVEL_DISTRICT = "district"
    LEVEL_NEIGHBORHOOD = "neighborhood"

    LEVEL_CHOICES = [
        (LEVEL_COUNTRY, _("Pays")),
        (LEVEL_PROVINCE, _("Province / région")),
        (LEVEL_CITY, _("Ville / commune")),
        (LEVEL_DISTRICT, _("District / zone")),
        (LEVEL_NEIGHBORHOOD, _("Quartier / localité")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="areas")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    level = models.CharField(max_length=40, default=LEVEL_CITY)
    level_label = models.CharField(max_length=80, blank=True)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, blank=True)
    alt_names = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "administrative_areas"
        unique_together = ("country", "parent", "name", "level")
        ordering = ["level", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def clean(self):
        if self.parent and self.parent.country_id != self.country_id:
            raise ValidationError(
                {"parent": _("La subdivision doit appartenir au même pays.")}
            )
        if self.level == self.LEVEL_COUNTRY and self.parent_id is not None:
            raise ValidationError(
                {"parent": _("Le niveau pays ne peut pas avoir de parent.")}
            )

    @property
    def location_path(self):
        path = []
        area = self
        while area is not None and area.country_id == self.country_id:
            path.append(area)
            area = area.parent
        return list(reversed(path))


class SellerPublicLocation(models.Model):
    """Localisation publique du vendeur : jamais l'adresse complète ni les coordonnées précises."""

    class Precision(models.TextChoices):
        COUNTRY = "country", _("Pays")
        PROVINCE = "province", _("Province / région")
        CITY = "city", _("Ville / commune")
        LOCALITY = "locality", _("Quartier / zone")
        CUSTOM = "custom", _("Autre")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="public_location",
    )
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="seller_public_locations"
    )
    administrative_area = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="public_seller_locations",
    )
    locality = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="public_locality_seller_locations",
    )
    precision = models.CharField(
        max_length=20, choices=Precision.choices, default=Precision.CITY
    )
    public_note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "seller_public_locations"

    def clean(self):
        if (
            self.administrative_area
            and self.administrative_area.country_id != self.country_id
        ):
            raise ValidationError(
                {
                    "administrative_area": _(
                        "La subdivision doit appartenir au pays sélectionné."
                    )
                }
            )
        if self.locality and self.locality.country_id != self.country_id:
            raise ValidationError(
                {"locality": _("La localité doit appartenir au pays sélectionné.")}
            )
        if (
            self.locality
            and self.administrative_area
            and self.locality.parent_id not in {self.administrative_area.pk, None}
        ):
            if self.locality.parent_id != self.administrative_area.pk:
                raise ValidationError(
                    {
                        "locality": _(
                            "La localité sélectionnée n'appartient pas à la subdivision choisie."
                        )
                    }
                )

    @property
    def display_name(self):
        preference = getattr(self.user, "location_preference", None)
        parts = []
        if self.country and (preference is None or preference.show_country):
            parts.append(self.country.name)
        show_admin_area = preference is None or preference.show_admin_area
        show_locality = preference is not None and preference.show_locality
        selected_area = self.locality or self.administrative_area
        path = selected_area.location_path if selected_area else []
        include_leaf = (
            self.locality is not None
            and show_locality
            and self.precision in {self.Precision.CITY, self.Precision.LOCALITY}
            and (
                self.locality.level != AdministrativeArea.LEVEL_NEIGHBORHOOD
                or self.precision == self.Precision.LOCALITY
            )
        )
        if self.precision == self.Precision.COUNTRY:
            path = []
        elif show_admin_area:
            if self.locality and not include_leaf:
                path = path[:-1]
        elif include_leaf:
            path = path[-1:]
        else:
            path = []
        parts.extend(area.name for area in path)
        if self.public_note and preference is not None and preference.show_public_note:
            parts.append(self.public_note)
        return ", ".join(parts)


class PrivateAddress(models.Model):
    """Adresse privée d'un profil : visible uniquement par son propriétaire et les personnes autorisées."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="private_addresses",
    )
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="private_addresses"
    )
    administrative_area = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="private_addresses",
    )
    locality = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="private_locality_addresses",
    )
    label = models.CharField(max_length=60, blank=True)
    street_address = models.TextField()
    landmark = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "private_addresses"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="unique_default_private_address_per_user",
            )
        ]
        ordering = ["-is_default", "-updated_at"]

    def clean(self):
        if (
            self.administrative_area
            and self.administrative_area.country_id != self.country_id
        ):
            raise ValidationError(
                {
                    "administrative_area": _(
                        "Cette subdivision ne correspond pas au pays de l'adresse."
                    )
                }
            )
        if self.locality and self.locality.country_id != self.country_id:
            raise ValidationError(
                {
                    "locality": _(
                        "Cette localité ne correspond pas au pays de l'adresse."
                    )
                }
            )
        if (
            self.locality
            and self.administrative_area
            and self.locality.parent_id not in {self.administrative_area.pk, None}
        ):
            if self.locality.parent_id != self.administrative_area.pk:
                raise ValidationError(
                    {
                        "locality": _(
                            "La localité sélectionnée n'appartient pas à la subdivision choisie."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        if self.is_default:
            PrivateAddress.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class PickupLocation(models.Model):
    """Lieu de remise pour une transaction de main à main ou de point de rencontre."""

    class LocationType(models.TextChoices):
        PUBLIC = "public", _("Public / général")
        AGREED = "agreed", _("Point de rencontre convenu")
        PRIVATE = "private", _("Privé / réservé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pickup_locations",
    )
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="pickup_locations"
    )
    administrative_area = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pickup_locations",
    )
    locality = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pickup_locality_locations",
    )
    name = models.CharField(max_length=120)
    location_type = models.CharField(
        max_length=20, choices=LocationType.choices, default=LocationType.PUBLIC
    )
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pickup_locations"
        ordering = ["name"]

    def clean(self):
        if (
            self.administrative_area
            and self.administrative_area.country_id != self.country_id
        ):
            raise ValidationError(
                {
                    "administrative_area": _(
                        "Cette subdivision ne correspond pas au pays du lieu."
                    )
                }
            )
        if self.locality and self.locality.country_id != self.country_id:
            raise ValidationError(
                {"locality": _("Cette localité ne correspond pas au pays du lieu.")}
            )


class DeliveryOption(models.Model):
    """Options de livraison réellement proposées par le vendeur."""

    class Mode(models.TextChoices):
        PICKUP = "pickup", _("Remise en main propre")
        IN_CITY = "in_city", _("Livraison dans la ville")
        IN_AREA = "in_area", _("Livraison dans certaines zones")
        IN_PROVINCE = "in_province", _("Livraison dans la province / région")
        NATIONAL = "national", _("Livraison nationale")
        INTERNATIONAL = "international", _("Livraison internationale")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_options",
    )
    mode = models.CharField(max_length=20, choices=Mode.choices)
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="delivery_options",
        null=True,
        blank=True,
    )
    administrative_area = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_area_options",
    )
    locality = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_locality_options",
    )
    coverage_areas = models.ManyToManyField(
        AdministrativeArea, blank=True, related_name="covered_by_delivery_options"
    )
    conditions = models.TextField(blank=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_delivery_days = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery_options"
        ordering = ["mode", "-is_active"]

    def clean(self):
        if (
            self.country
            and self.administrative_area
            and self.administrative_area.country_id != self.country_id
        ):
            raise ValidationError(
                {
                    "administrative_area": _(
                        "La zone desservie doit appartenir au pays sélectionné."
                    )
                }
            )
        if (
            self.country
            and self.locality
            and self.locality.country_id != self.country_id
        ):
            raise ValidationError(
                {
                    "locality": _(
                        "La localité desservie doit appartenir au pays sélectionné."
                    )
                }
            )
        if (
            self.locality
            and self.administrative_area
            and self.locality.parent_id not in {self.administrative_area.pk, None}
        ):
            if self.locality.parent_id != self.administrative_area.pk:
                raise ValidationError(
                    {
                        "locality": _(
                            "La localité n'appartient pas à la subdivision choisie."
                        )
                    }
                )

    @property
    def public_label(self):
        if self.mode == self.Mode.PICKUP:
            return "Remise en main propre"
        if self.mode == self.Mode.IN_CITY:
            return "Livraison dans la ville"
        if self.mode == self.Mode.IN_AREA:
            return "Livraison dans certaines zones"
        if self.mode == self.Mode.IN_PROVINCE:
            return "Livraison dans la province"
        if self.mode == self.Mode.NATIONAL:
            return "Livraison nationale"
        return "Livraison internationale"


class SellerLocationPreference(models.Model):
    """Préférence de confidentialité de la localisation publique du vendeur."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_preference",
    )
    show_country = models.BooleanField(default=True)
    show_admin_area = models.BooleanField(default=True)
    show_locality = models.BooleanField(default=False)
    show_public_note = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "seller_location_preferences"
