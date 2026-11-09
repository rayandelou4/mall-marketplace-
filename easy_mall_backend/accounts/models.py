"""
Modèles de l'app `accounts`.

Gère : l'utilisateur unique (acheteur + vendeur confondus), la vérification
de l'e-mail et du numéro de téléphone, et les préférences de thème.

Placer `AUTH_USER_MODEL = "accounts.User"` dans settings.py AVANT la première
migration (impossible de changer de modèle utilisateur après coup sans
opération lourde).
"""

import random
import secrets
import string
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):

    """Manager custom : l'authentification se fait par e-mail, pas par username."""

    use_in_migrations = True

    def get_by_natural_key(self, email):
        # Django.normalize_email ne met en minuscule que le domaine (pas la
        # partie locale) : sans ce __iexact, "Jean@Exemple.com" et
        # "jean@exemple.com" seraient deux recherches différentes à la
        # connexion, alors qu'ils désignent en pratique le même compte.
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": email})

    def _create_user(self, email, phone_number, username, password, **extra_fields):
        if not email:
            raise ValueError(_("L'adresse e-mail est obligatoire."))
        if not phone_number:
            raise ValueError(_("Le numéro de téléphone est obligatoire."))

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            phone_number=phone_number,
            username=username,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, phone_number, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone_number, username, password, **extra_fields)

    def create_superuser(self, email, phone_number, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("is_phone_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Le superuser doit avoir is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Le superuser doit avoir is_superuser=True."))

        return self._create_user(email, phone_number, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur unique de la plateforme : chaque compte peut acheter ET vendre.
    Le type vendeur est explicitement enregistré afin de distinguer les
    particuliers des commerçants sans créer un second système d'authentification.
    """

    class AuthProvider(models.TextChoices):
        LOCAL = "local", _("Local")
        GOOGLE = "google", _("Google")

    class SellerType(models.TextChoices):
        INDIVIDUAL = "individual", _("Particulier")
        PROFESSIONAL = "professional", _("Commerçant professionnel")

    class ThemePreference(models.TextChoices):
        LIGHT = "light", _("Clair")
        DARK = "dark", _("Sombre")
        SYSTEM = "system", _("Système")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(_("adresse e-mail"), unique=True)
    phone_number = models.CharField(_("numéro de téléphone"), max_length=20, unique=True)
    show_phone_on_listings = models.BooleanField(default=False)
    username = models.SlugField(_("nom d'utilisateur"), max_length=50, unique=True)

    first_name = models.CharField(_("prénom"), max_length=100, blank=True)
    last_name = models.CharField(_("nom"), max_length=100, blank=True)
    avatar_url = models.URLField(_("photo de profil"), blank=True, null=True)
    bio = models.TextField(_("biographie"), blank=True)

    city = models.CharField(_("ville"), max_length=100, blank=True)
    country = models.CharField(_("pays"), max_length=100, blank=True)

    seller_type = models.CharField(
        _("type de vendeur"),
        max_length=20,
        choices=SellerType.choices,
        default=SellerType.INDIVIDUAL,
    )
    shop_name = models.CharField(_("nom de la boutique"), max_length=150, blank=True)
    shop_description = models.TextField(_("description de la boutique"), blank=True)
    shop_logo_url = models.URLField(_("logo de la boutique"), blank=True, null=True)
    shop_cover_url = models.URLField(_("image de couverture de la boutique"), blank=True, null=True)

    is_email_verified = models.BooleanField(_("e-mail vérifié"), default=False)
    is_phone_verified = models.BooleanField(_("téléphone vérifié"), default=False)

    auth_provider = models.CharField(
        max_length=10, choices=AuthProvider.choices, default=AuthProvider.LOCAL
    )
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    theme_preference = models.CharField(
        max_length=10, choices=ThemePreference.choices, default=ThemePreference.SYSTEM
    )

    # Réputation — dénormalisé pour éviter de recalculer à chaque affichage de profil.
    # Recalculé par un signal/tâche Celery à chaque nouvel avis (voir app `reviews`).
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_sales = models.PositiveIntegerField(default=0)
    total_purchases = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(_("actif"), default=True)
    is_staff = models.BooleanField(_("accès admin"), default=False)
    is_suspended = models.BooleanField(_("compte suspendu"), default=False)
    suspension_reason = models.TextField(blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_previous_is_active = models.BooleanField(default=True)
    suspended_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts_suspended",
    )

    date_joined = models.DateTimeField(_("date d'inscription"), default=timezone.now)
    # `last_login` est déjà fourni par AbstractBaseUser.

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "phone_number"]

    class Meta:
        db_table = "users"
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["city", "country"]),
        ]

    def __str__(self):
        return self.username or self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def is_fully_verified(self):
        # Vérification téléphone désactivée pour l'instant (SMS retiré du
        # parcours) : seul l'e-mail conditionne le statut "vérifié". Le champ
        # is_phone_verified et le modèle PhoneOTP restent en base, dormants,
        # pour une réactivation ultérieure sans tout reconstruire.
        return self.is_email_verified


class EmailVerificationToken(models.Model):
    """Code à usage unique envoyé par e-mail pour valider l'adresse."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="email_verification_tokens"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=6, default="", editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    MAX_ATTEMPTS = 5

    class Meta:
        db_table = "email_verification_tokens"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = "".join(secrets.choice(string.digits) for _ in range(6))
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
            not self.is_used
            and self.attempts < self.MAX_ATTEMPTS
            and timezone.now() < self.expires_at
        )


class PhoneOTP(models.Model):
    """Code OTP à 6 chiffres envoyé par SMS pour valider le numéro de téléphone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="phone_otps")
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    MAX_ATTEMPTS = 5

    class Meta:
        db_table = "phone_otps"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
            not self.is_used
            and self.attempts < self.MAX_ATTEMPTS
            and timezone.now() < self.expires_at
        )


class PasswordResetToken(models.Model):
    """Code à usage unique envoyé par e-mail pour réinitialiser le mot de passe."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=6, default="", editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_tokens"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = "".join(random.choices(string.digits, k=6))
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
