"""
Modèles de l'app `catalog`.

Gère : les catégories (arborescence), les produits publiés par les
utilisateurs, leurs images/vidéo, les favoris et les recherches sauvegardées.
"""

import hashlib
import unicodedata
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    """Catégorie de produits, avec sous-catégories via `parent`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("nom"), max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    icon_url = models.URLField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        verbose_name = _("catégorie")
        verbose_name_plural = _("catégories")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_subcategory(self):
        return self.parent_id is not None


def _normalize_identity_part(value, compact=False):
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    characters = []
    for character in normalized:
        if unicodedata.category(character) == "Mn":
            continue
        if unicodedata.category(character)[0] in {"L", "N"}:
            characters.append(character)
        elif not compact and characters and characters[-1] != " ":
            characters.append(" ")
    return "".join(characters).strip()


class ProductIdentity(models.Model):
    """Référentiel administré des produits communs à plusieurs annonces."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="product_identities"
    )
    name = models.CharField(max_length=180)
    brand = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=150, blank=True)
    manufacturer_reference = models.CharField(max_length=100, blank=True)
    variant = models.CharField(max_length=150, blank=True)
    comparison_key = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_identities"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        has_reference = bool(_normalize_identity_part(self.manufacturer_reference, compact=True))
        has_structured_variant = all(
            _normalize_identity_part(value)
            for value in (self.brand, self.model_name, self.variant)
        )
        if not has_reference and not has_structured_variant:
            raise ValidationError(
                "Une référence fabricant ou une marque, un modèle et une variante sont requis."
            )

    def save(self, *args, **kwargs):
        reference = _normalize_identity_part(self.manufacturer_reference, compact=True)
        if reference:
            key_parts = (
                str(self.category_id),
                "reference",
                _normalize_identity_part(self.brand),
                reference,
            )
        else:
            key_parts = (
                str(self.category_id),
                "attributes",
                _normalize_identity_part(self.brand),
                _normalize_identity_part(self.model_name),
                _normalize_identity_part(self.variant),
            )
        self.comparison_key = hashlib.sha256("|".join(key_parts).encode()).hexdigest()
        self.full_clean()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"comparison_key"}
        super().save(*args, **kwargs)


class Product(models.Model):
    """Annonce publiée par un utilisateur (le "vendeur" pour cette annonce)."""

    class ItemType(models.TextChoices):
        PRODUCT = "product", _("Produit")
        SERVICE = "service", _("Service")

    class PriceUnit(models.TextChoices):
        FIXED = "fixed", _("Forfait")
        HOUR = "hour", _("Par heure")
        DAY = "day", _("Par jour")

    class Condition(models.TextChoices):
        NEUF = "neuf", _("Neuf")
        COMME_NEUF = "comme_neuf", _("Comme neuf")
        BON_ETAT = "bon_etat", _("Bon état")
        SATISFAISANT = "satisfaisant", _("Satisfaisant")
        A_RECONDITIONNER = "a_reconditionner", _("À reconditionner")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Brouillon")
        PUBLISHED = "published", _("Publié")
        SOLD = "sold", _("Vendu")
        ARCHIVED = "archived", _("Archivé")

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", _("En attente")
        APPROVED = "approved", _("Approuvé")
        REJECTED = "rejected", _("Rejeté")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    comparison_identity = models.ForeignKey(
        ProductIdentity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )

    item_type = models.CharField(max_length=10, choices=ItemType.choices, default=ItemType.PRODUCT)
    title = models.CharField(_("titre"), max_length=150)
    description = models.TextField(_("description"))

    price = models.DecimalField(
        _("prix"), max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default="USD")
    price_unit = models.CharField(max_length=10, choices=PriceUnit.choices, default=PriceUnit.FIXED)

    condition = models.CharField(max_length=20, choices=Condition.choices, blank=True, default="")

    city = models.CharField(_("ville"), max_length=100)
    country = models.CharField(_("pays"), max_length=100)

    stock_quantity = models.PositiveIntegerField(_("stock disponible"), default=1)
    shipping_cost = models.DecimalField(
        _("frais de livraison"), max_digits=10, decimal_places=2, default=0
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    moderation_status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.PENDING
    )
    is_suspended = models.BooleanField(default=False, db_index=True)
    suspension_reason = models.TextField(blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suspended_products",
    )
    status_before_suspension = models.CharField(
        max_length=10,
        choices=Status.choices,
        blank=True,
        default="",
    )

    # Compteurs dénormalisés — incrémentés côté vue/serializer, pas recalculés à la volée.
    views_count = models.PositiveIntegerField(default=0)
    favorites_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        verbose_name = _("produit")
        verbose_name_plural = _("produits")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "status", "moderation_status"]),
            models.Index(fields=["city", "country"]),
            models.Index(fields=["price"]),
            models.Index(
                fields=["comparison_identity", "currency", "status", "moderation_status"],
                name="product_cmp_group_idx",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.comparison_identity_id
            and self.comparison_identity.category_id != self.category_id
        ):
            raise ValidationError(
                {"comparison_identity": "L'identité doit appartenir à la catégorie de l'annonce."}
            )

    @property
    def is_available(self):
        return (
            not self.is_suspended
            and self.item_type == self.ItemType.PRODUCT
            and self.status == self.Status.PUBLISHED
            and self.moderation_status == self.ModerationStatus.APPROVED
            and self.stock_quantity > 0
        )


class ProductImage(models.Model):
    """
    Image d'un produit. Limite de 3 images par produit (cahier des charges).
    La contrainte est vérifiée ici via `clean()` (appelé par `full_clean()`) ET
    doit être re-vérifiée côté serializer DRF au moment de l'upload, car
    `save()` seul n'appelle pas automatiquement `full_clean()` en Django.
    """

    MAX_IMAGES_PER_PRODUCT = 3

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField()
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "product_images"
        ordering = ["order"]

    def __str__(self):
        return f"Image {self.order} — {self.product.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        existing_count = ProductImage.objects.filter(product=self.product).exclude(
            pk=self.pk
        ).count()
        if existing_count >= self.MAX_IMAGES_PER_PRODUCT:
            raise ValidationError(
                _("Un produit ne peut avoir plus de %(max)s images.")
                % {"max": self.MAX_IMAGES_PER_PRODUCT}
            )


class ProductVideo(models.Model):
    """Vidéo optionnelle et unique par produit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="video")
    video_url = models.URLField()

    class Meta:
        db_table = "product_videos"

    def __str__(self):
        return f"Vidéo — {self.product.title}"


class Favorite(models.Model):
    """Produit ajouté aux favoris par un utilisateur."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorites"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_user_favorite")
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"


class SellerFavorite(models.Model):
    """Vendeur suivi par un utilisateur connecté."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_favorites"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "seller_favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "seller"], name="unique_user_seller_favorite")
        ]

    def __str__(self):
        return f"{self.user} suit {self.seller}"


class SavedSearch(models.Model):
    """Recherche (filtres) sauvegardée par un utilisateur pour la retrouver rapidement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_searches"
    )
    name = models.CharField(max_length=100, blank=True)
    query_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saved_searches"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"Recherche du {self.created_at:%d/%m/%Y}"