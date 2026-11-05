"""
Serializers de l'app `accounts`.
"""

import random
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import EmailVerificationToken, PasswordResetToken, PhoneOTP, User
from .tasks import (
    send_password_reset_email_task,
    send_phone_otp_task,
    send_verification_email_task,
)


def _generate_otp_code():
    return "".join(random.choices(string.digits, k=6))


class UserSerializer(serializers.ModelSerializer):
    """Profil public : uniquement les informations non sensibles du vendeur."""

    full_name = serializers.ReadOnlyField()
    seller_type_display = serializers.CharField(
        source="get_seller_type_display", read_only=True
    )
    city = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    public_location_display = serializers.SerializerMethodField()
    verification_badges = serializers.SerializerMethodField()

    def get_city(self, obj):
        location = getattr(obj, "public_location", None)
        preference = getattr(obj, "location_preference", None)
        if (
            location is None
            or preference is None
            or not preference.show_locality
            or location.precision
            not in {location.Precision.CITY, location.Precision.LOCALITY}
            or location.locality is None
            or (
                location.locality.level == "neighborhood"
                and location.precision != location.Precision.LOCALITY
            )
        ):
            return ""
        return location.locality.name

    def get_country(self, obj):
        location = getattr(obj, "public_location", None)
        preference = getattr(obj, "location_preference", None)
        if location is None or (preference is not None and not preference.show_country):
            return ""
        return location.country.name

    def get_public_location_display(self, obj):
        location = getattr(obj, "public_location", None)
        return location.display_name if location is not None else ""

    def get_verification_badges(self, obj):
        from seller_verification.models import VerificationLevel
        from seller_verification.services import CertificationCalculator

        labels = {
            VerificationLevel.LEVEL_0_PROFILE_CREATED: (
                "Profil créé",
                "Un compte actif existe. Cela ne confirme ni l'identité ni la fiabilité.",
            ),
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED: (
                "E-mail vérifié",
                "L'adresse e-mail a été confirmée; ce n'est pas une preuve d'identité.",
            ),
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED: (
                "Identité examinée",
                "Examen interne d'un justificatif; l'authenticité du document n'est pas garantie.",
            ),
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED: (
                "Commerçant professionnel vérifié",
                "Examen interne d'éléments d'activité; cela ne prouve pas l'identité personnelle du propriétaire.",
            ),
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY: (
                "Historique commercial fiable",
                "Indicateur calculé depuis les ventes terminées, avis transactionnels et annulations.",
            ),
        }
        levels = {VerificationLevel.LEVEL_0_PROFILE_CREATED}
        if obj.is_email_verified:
            levels.add(VerificationLevel.LEVEL_1_EMAIL_VERIFIED)
        levels.update(
            obj.certifications.filter(revoked_at__isnull=True)
            .exclude(level=VerificationLevel.LEVEL_4_RELIABLE_HISTORY)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .values_list("level", flat=True)
        )
        if CertificationCalculator._qualifies_for_reliable_history(obj):
            levels.add(VerificationLevel.LEVEL_4_RELIABLE_HISTORY)
        return [
            {"level": level, "label": labels[level][0], "meaning": labels[level][1]}
            for level in labels
            if level in levels
        ]

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "first_name",
            "last_name",
            "avatar_url",
            "bio",
            "city",
            "country",
            "public_location_display",
            "verification_badges",
            "seller_type",
            "seller_type_display",
            "shop_name",
            "shop_description",
            "shop_logo_url",
            "shop_cover_url",
            "average_rating",
            "total_sales",
            "total_purchases",
            "theme_preference",
            "date_joined",
        ]
        read_only_fields = fields


class MeSerializer(UserSerializer):
    """
    Profil de l'utilisateur connecté à lui-même (réponse de connexion, GET /me/).
    Ajoute `is_staff` — jamais exposé sur un profil public (UserSerializer),
    pour ne pas révéler publiquement qui fait partie du staff.
    """

    is_fully_verified = serializers.ReadOnlyField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            "is_staff",
            "is_email_verified",
            "is_fully_verified",
        ]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour sécurisée du profil et du type vendeur par son propriétaire."""

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "avatar_url",
            "bio",
            "city",
            "country",
            "seller_type",
            "shop_name",
            "shop_description",
            "shop_logo_url",
            "shop_cover_url",
            "theme_preference",
        ]

    def validate_seller_type(self, value):
        allowed = {User.SellerType.INDIVIDUAL, User.SellerType.PROFESSIONAL}
        if value not in allowed:
            raise serializers.ValidationError("Type de vendeur invalide.")
        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    seller_type = serializers.ChoiceField(
        choices=User.SellerType.choices,
        required=False,
        default=User.SellerType.INDIVIDUAL,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "phone_number",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
            "seller_type",
            "shop_name",
            "shop_description",
            "shop_logo_url",
            "shop_cover_url",
            "password",
            "password_confirm",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Les deux mots de passe ne correspondent pas."}
            )
        if attrs.get("seller_type") not in {
            User.SellerType.INDIVIDUAL,
            User.SellerType.PROFESSIONAL,
        }:
            raise serializers.ValidationError(
                {"seller_type": "Type de vendeur invalide."}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")

        with transaction.atomic():
            user = User.objects.create_user(
                password=password,
                is_active=False,
                is_email_verified=False,
                **validated_data,
            )

            # Vérification e-mail (code 24h) — seule étape d'activation du compte.
            token = EmailVerificationToken.objects.create(
                user=user, expires_at=timezone.now() + timedelta(hours=24)
            )

            try:
                send_verification_email_task.run(str(user.id), str(token.code))
            except Exception as exc:
                raise serializers.ValidationError(
                    {
                        "email": "L'envoi de l'e-mail de confirmation a échoué. L'inscription a été annulée."
                    }
                ) from exc

            return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Ajoute des infos utilisateur au JWT et à la réponse de connexion."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["seller_type"] = user.seller_type
        token["is_fully_verified"] = user.is_fully_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        if not user.is_active or not user.is_email_verified:
            raise serializers.ValidationError(
                {
                    "detail": "Veuillez vérifier votre adresse e-mail avant de pouvoir vous connecter."
                }
            )

        data["user"] = MeSerializer(user).data
        return data


class EmailVerificationConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        code = attrs["code"]
        if not code.isdigit():
            raise serializers.ValidationError(
                {"code": "Le code de vérification doit contenir 6 chiffres."}
            )

        request = self.context.get("request")
        user = None

        if request and getattr(request, "user", None) and request.user.is_authenticated:
            user = request.user
        elif attrs.get("email"):
            try:
                user = User.objects.get(email__iexact=attrs["email"])
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"email": "Aucun compte trouvé pour cet e-mail."}
                )
        else:
            raise serializers.ValidationError(
                {"email": "L'e-mail est requis pour vérifier le code."}
            )

        verification = (
            EmailVerificationToken.objects.filter(
                user=user,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )
        if not verification or not verification.is_valid():
            raise serializers.ValidationError(
                {
                    "code": "Code invalide ou expiré. Demandez un nouveau code pour recevoir un code frais."
                }
            )
        if not secrets.compare_digest(verification.code, code):
            EmailVerificationToken.objects.filter(
                pk=verification.pk,
                attempts__lt=EmailVerificationToken.MAX_ATTEMPTS,
            ).update(attempts=F("attempts") + 1)
            raise serializers.ValidationError(
                {
                    "code": "Code invalide ou expiré. Demandez un nouveau code pour recevoir un code frais."
                }
            )

        self.verification = verification
        return attrs

    def save(self):
        with transaction.atomic():
            token_updated = EmailVerificationToken.objects.filter(
                pk=self.verification.pk,
                code=self.verification.code,
                is_used=False,
                attempts__lt=EmailVerificationToken.MAX_ATTEMPTS,
                expires_at__gt=timezone.now(),
            ).update(is_used=True)
            if not token_updated:
                raise serializers.ValidationError(
                    {"code": "Code déjà utilisé ou expiré."}
                )
            user = self.verification.user
            user.is_email_verified = True
            user.is_active = True
            user.save(update_fields=["is_email_verified", "is_active"])
        return user


class PhoneOTPRequestSerializer(serializers.Serializer):
    """Aucune donnée d'entrée : génère et envoie un nouvel OTP à `request.user`."""

    def save(self):
        user = self.context["request"].user
        code = _generate_otp_code()
        otp = PhoneOTP.objects.create(
            user=user, code=code, expires_at=timezone.now() + timedelta(minutes=10)
        )
        send_phone_otp_task.delay(str(user.id), code)
        return otp


class PhoneOTPVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)

    def validate_code(self, value):
        user = self.context["request"].user
        otp = (
            PhoneOTP.objects.filter(user=user, code=value)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid():
            last_otp = (
                PhoneOTP.objects.filter(user=user).order_by("-created_at").first()
            )
            if last_otp:
                last_otp.attempts += 1
                last_otp.save(update_fields=["attempts"])
            raise serializers.ValidationError("Code invalide ou expiré.")
        self.otp = otp
        return value

    def save(self):
        user = self.context["request"].user
        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])
        self.otp.is_used = True
        self.otp.save(update_fields=["is_used"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Ne révèle jamais si l'e-mail existe ou non (évite l'énumération de comptes)."""

    email = serializers.EmailField()

    def save(self):
        email = self.validated_data["email"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return
        token = PasswordResetToken.objects.create(
            user=user, expires_at=timezone.now() + timedelta(hours=1)
        )
        task_args = (str(user.id), str(token.code))
        if settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER:
            send_password_reset_email_task.run(*task_args)
        else:
            try:
                send_password_reset_email_task.delay(*task_args)
            except OperationalError:
                send_password_reset_email_task.run(*task_args)


class PasswordResetCodeVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        if not attrs["code"].isdigit():
            raise serializers.ValidationError(
                {"code": "Le code doit contenir 6 chiffres."}
            )

        try:
            user = User.objects.get(email__iexact=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"code": "Code invalide ou expiré."})

        reset_token = (
            PasswordResetToken.objects.filter(user=user, code=attrs["code"])
            .order_by("-created_at")
            .first()
        )
        if not reset_token or not reset_token.is_valid():
            raise serializers.ValidationError(
                {"code": "Code invalide ou expiré. Demandez un nouveau code."}
            )

        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )

    def validate(self, attrs):
        if not attrs["code"].isdigit():
            raise serializers.ValidationError(
                {"code": "Le code doit contenir 6 chiffres."}
            )

        try:
            user = User.objects.get(email__iexact=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"code": "Code invalide ou expiré."})

        reset_token = (
            PasswordResetToken.objects.filter(user=user, code=attrs["code"])
            .order_by("-created_at")
            .first()
        )
        if not reset_token or not reset_token.is_valid():
            raise serializers.ValidationError(
                {"code": "Code invalide ou expiré. Demandez un nouveau code."}
            )
        self.reset_token = reset_token
        return attrs

    def save(self):
        user = self.reset_token.user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        self.reset_token.is_used = True
        self.reset_token.save(update_fields=["is_used"])
        return user


class ResendEmailVerificationSerializer(serializers.Serializer):
    """Renvoie un nouveau code à un utilisateur connecté ou à un compte non vérifié ciblé."""

    email = serializers.EmailField(required=False)
    RESEND_COOLDOWN_SECONDS = 30

    def validate(self, attrs):
        request = self.context["request"]
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            if user.is_email_verified:
                raise serializers.ValidationError("Cet e-mail est déjà vérifié.")
            last_token = (
                EmailVerificationToken.objects.filter(user=user)
                .order_by("-created_at")
                .first()
            )
            if last_token and timezone.now() < last_token.created_at + timedelta(
                seconds=self.RESEND_COOLDOWN_SECONDS
            ):
                remaining = int(
                    (
                        last_token.created_at
                        + timedelta(seconds=self.RESEND_COOLDOWN_SECONDS)
                        - timezone.now()
                    ).total_seconds()
                )
                raise serializers.ValidationError(
                    {
                        "detail": f"Veuillez attendre {remaining} secondes avant de renvoyer un nouveau code."
                    }
                )
            attrs["user"] = user
            return attrs

        if not attrs.get("email"):
            raise serializers.ValidationError(
                {"email": "L'e-mail est requis pour renvoyer le code."}
            )

        try:
            user = User.objects.get(email__iexact=attrs["email"])
        except User.DoesNotExist:
            return attrs

        if user.is_email_verified:
            raise serializers.ValidationError("Cet e-mail est déjà vérifié.")

        last_token = (
            EmailVerificationToken.objects.filter(user=user)
            .order_by("-created_at")
            .first()
        )
        if last_token and timezone.now() < last_token.created_at + timedelta(
            seconds=self.RESEND_COOLDOWN_SECONDS
        ):
            remaining = int(
                (
                    last_token.created_at
                    + timedelta(seconds=self.RESEND_COOLDOWN_SECONDS)
                    - timezone.now()
                ).total_seconds()
            )
            raise serializers.ValidationError(
                {
                    "detail": f"Veuillez attendre {remaining} secondes avant de renvoyer un nouveau code."
                }
            )

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data.get("user")
        if not user:
            return None

        EmailVerificationToken.objects.filter(user=user, is_used=False).update(
            is_used=True
        )
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() + timedelta(hours=24)
        )
        task_args = (str(user.id), str(token.code))
        if settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER:
            send_verification_email_task.run(*task_args)
        else:
            try:
                send_verification_email_task.delay(*task_args)
            except OperationalError:
                send_verification_email_task.run(*task_args)
        return token


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
