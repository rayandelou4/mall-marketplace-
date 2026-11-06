"""
Serializers pour le système de certification des vendeurs.
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    SellerCertification,
    VerificationRequest,
    VerificationDocument,
    VerificationCriteria,
    RiskSignal,
    VerificationLevel,
    VerificationRequestStatus,
    VerificationType,
)


class VerificationDocumentSerializer(serializers.ModelSerializer):
    """Serializer pour les documents de vérification (lecture seule pour les utilisateurs)."""

    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDocument
        fields = [
            "id",
            "document_type",
            "file_size",
            "file_size_mb",
            "description",
            "is_valid_format",
            "uploaded_at",
            "validated_at",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj: VerificationDocument) -> str:
        """Génère l'URL de téléchargement sécurisée."""
        request = self.context.get("request")
        if (
            request
            and request.user.is_staff
            and request.user.has_perm("seller_verification.view_verificationdocument")
        ):
            # Seuls les administrateurs autorisés peuvent télécharger les documents
            return request.build_absolute_uri(
                f"/api/v1/seller-verification/documents/{obj.id}/download/"
            )
        return ""

    def get_file_size_mb(self, obj: VerificationDocument) -> float:
        """Retourne la taille en Mo avec 2 décimales."""
        return round(obj.file_size / (1024 * 1024), 2)


class VerificationRequestSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes de vérification."""

    user_display_name = serializers.CharField(source="user.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    verification_type_display = serializers.CharField(
        source="get_verification_type_display", read_only=True
    )
    target_level_display = serializers.CharField(
        source="get_target_level_display", read_only=True
    )
    days_until_expiry = serializers.IntegerField(read_only=True)
    documents = VerificationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = VerificationRequest
        fields = [
            "id",
            "user",
            "user_display_name",
            "verification_type",
            "verification_type_display",
            "target_level",
            "target_level_display",
            "status",
            "status_display",
            "description",
            "seller_message",
            "submitted_at",
            "expires_at",
            "days_until_expiry",
            "rejection_reason",
            "created_at",
            "updated_at",
            "documents",
        ]
        read_only_fields = [
            "id",
            "user",
            "submitted_at",
            "expires_at",
            "reviewed_by",
            "reviewed_at",
            "decision_notes",
            "seller_message",
            "rejection_reason",
            "created_at",
            "updated_at",
            "documents",
        ]

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validation de la demande."""
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise PermissionDenied("Authentification requise.")

        if "status" in data or "reviewed_by" in data or "reviewed_at" in data:
            raise serializers.ValidationError(
                "Le statut et les décisions sont gérés par la plateforme."
            )

        # L'utilisateur ne peut créer des demandes que pour lui-même
        if self.instance is None:  # Création
            data["user"] = request.user
        elif self.instance.user != request.user:
            raise PermissionDenied("Vous ne pouvez modifier que vos propres demandes.")

        # Validation spécifique au type de vérification
        verification_type = data.get(
            "verification_type", getattr(self.instance, "verification_type", None)
        )
        target_level = data.get(
            "target_level", getattr(self.instance, "target_level", None)
        )
        request_user = self.instance.user if self.instance else request.user

        if target_level not in {
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED,
        }:
            raise ValidationError(
                {"target_level": "Ce niveau ne nécessite pas de demande documentaire."}
            )

        # Vérification de la cohérence niveau/type
        if verification_type == VerificationType.IDENTITY_DOCUMENT:
            if target_level != VerificationLevel.LEVEL_2_IDENTITY_VERIFIED:
                raise ValidationError(
                    {
                        "target_level": "Les documents d'identité sont requis pour le niveau 2 (Identité examinée)."
                    }
                )

        elif verification_type == VerificationType.BUSINESS_REGISTRATION:
            if target_level != VerificationLevel.LEVEL_3_BUSINESS_VERIFIED:
                raise ValidationError(
                    {
                        "target_level": "Les enregistrements commerciaux sont requis pour le niveau 3 (Commerçant professionnel vérifié)."
                    }
                )

        if (
            target_level == VerificationLevel.LEVEL_2_IDENTITY_VERIFIED
            and verification_type != VerificationType.IDENTITY_DOCUMENT
        ):
            raise ValidationError(
                {
                    "verification_type": "Le niveau identité requiert un justificatif d'identité."
                }
            )
        if (
            target_level == VerificationLevel.LEVEL_3_BUSINESS_VERIFIED
            and verification_type
            not in {
                VerificationType.BUSINESS_REGISTRATION,
                VerificationType.BUSINESS_LOCATION,
                VerificationType.BUSINESS_ACTIVITY_PROOF,
            }
        ):
            raise ValidationError(
                {
                    "verification_type": "Le niveau professionnel requiert une preuve d'activité."
                }
            )

        if (
            target_level == VerificationLevel.LEVEL_3_BUSINESS_VERIFIED
            and request_user.seller_type != request.user.SellerType.PROFESSIONAL
        ):
            raise ValidationError(
                {
                    "target_level": "La vérification commerciale est réservée aux comptes déclarés professionnels."
                }
            )

        if (
            target_level
            in {
                VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
                VerificationLevel.LEVEL_3_BUSINESS_VERIFIED,
            }
            and not request.user.is_email_verified
        ):
            raise ValidationError(
                {
                    "target_level": "Confirmez votre adresse e-mail avant de demander cet examen."
                }
            )

        return data

    def create(self, validated_data: Dict[str, Any]) -> VerificationRequest:
        """Crée une nouvelle demande."""
        request = self.context.get("request")
        if not request:
            raise PermissionDenied("Authentification requise.")

        validated_data["user"] = request.user
        validated_data["status"] = VerificationRequestStatus.DRAFT

        # Vérifier si l'utilisateur a déjà une certification pour ce niveau
        existing_certification = (
            SellerCertification.objects.filter(
                user=request.user,
                level=validated_data["target_level"],
                revoked_at__isnull=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .first()
        )

        if existing_certification:
            raise ValidationError(
                {
                    "target_level": f"Vous avez déjà une certification active pour le niveau {existing_certification.get_level_display()}."
                }
            )

        existing_request = VerificationRequest.objects.filter(
            user=request.user,
            verification_type=validated_data["verification_type"],
            status__in=[
                VerificationRequestStatus.DRAFT,
                VerificationRequestStatus.PENDING,
                VerificationRequestStatus.UNDER_REVIEW,
                VerificationRequestStatus.NEEDS_MORE_INFORMATION,
            ],
        ).exists()
        if existing_request:
            raise ValidationError(
                {
                    "detail": "Une demande active existe déjà pour ce type de vérification."
                }
            )

        return super().create(validated_data)


class VerificationRequestSubmitSerializer(serializers.Serializer):
    """Serializer pour soumettre une demande de vérification."""

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validation avant soumission."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise PermissionDenied("Authentification requise.")

        verification_request = self.context.get("verification_request")
        if not verification_request:
            raise ValidationError("Demande de vérification non trouvée.")

        if verification_request.user != request.user:
            raise PermissionDenied("Vous ne pouvez soumettre que vos propres demandes.")

        if verification_request.status not in {
            VerificationRequestStatus.DRAFT,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        }:
            raise ValidationError(
                "Cette demande ne peut pas être soumise dans son état actuel."
            )

        # Vérifier qu'il y a au moins un document
        if not verification_request.documents.exists():
            raise ValidationError(
                "Au moins un document doit être téléchargé avant de soumettre la demande."
            )

        # Vérifier que tous les documents ont un format valide
        invalid_docs = verification_request.documents.filter(is_valid_format=False)
        if invalid_docs.exists():
            raise ValidationError(
                "Tous les documents doivent avoir un format valide avant soumission."
            )

        return data

    def save(self) -> VerificationRequest:
        """Soumet la demande."""
        verification_request = self.context.get("verification_request")
        verification_request.submit()

        # Log d'audit
        from .models import CertificationAuditLog

        CertificationAuditLog.objects.create(
            user=verification_request.user,
            request=verification_request,
            action=CertificationAuditLog.ActionType.REQUEST_SUBMITTED,
            actor=verification_request.user,
            details={"status": verification_request.status},
        )

        return verification_request


class VerificationDocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer pour télécharger un document de vérification."""

    class Meta:
        model = VerificationDocument
        fields = [
            "id",
            "document_type",
            "file",
            "description",
        ]
        extra_kwargs = {
            "file": {"write_only": True},
        }

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validation du document."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise PermissionDenied("Authentification requise.")

        verification_request = self.context.get("verification_request")
        if not verification_request:
            raise ValidationError("Demande de vérification non trouvée.")

        if verification_request.user != request.user:
            raise PermissionDenied(
                "Vous ne pouvez ajouter des documents qu'à vos propres demandes."
            )

        if verification_request.status not in {
            VerificationRequestStatus.DRAFT,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        }:
            raise ValidationError(
                "Les documents ne peuvent pas être modifiés dans cet état."
            )

        if verification_request.documents.count() >= 5:
            raise ValidationError(
                {"file": "Une demande peut contenir au maximum cinq justificatifs."}
            )

        # Validation du fichier
        file = data.get("file")
        if file:
            # Vérification de la taille
            max_size = VerificationDocument.MAX_FILE_SIZE
            if file.size > max_size:
                raise ValidationError(
                    {
                        "file": f"Le fichier est trop volumineux. Taille maximale : {max_size // (1024 * 1024)} Mo"
                    }
                )

            # Vérification de l'extension
            ext = os.path.splitext(file.name)[1].lower()
            allowed_extensions = VerificationDocument.ALLOWED_EXTENSIONS
            if ext.lstrip(".") not in allowed_extensions:
                raise ValidationError(
                    {
                        "file": f"Extension de fichier non autorisée. Extensions autorisées : {', '.join(allowed_extensions)}"
                    }
                )

            file.seek(0)
            signature = file.read(16)
            file.seek(0)
            actual_mime = self._mime_from_signature(signature)
            extension_mimes = {
                ".jpg": {"image/jpeg"},
                ".jpeg": {"image/jpeg"},
                ".png": {"image/png"},
                ".pdf": {"application/pdf"},
                ".heic": {"image/heic"},
                ".heif": {"image/heif"},
            }
            if actual_mime not in extension_mimes.get(ext, set()):
                raise ValidationError(
                    {
                        "file": "Le contenu réel du fichier ne correspond pas à son extension."
                    }
                )
            data["mime_type"] = actual_mime
            data["original_filename"] = Path(file.name).name[:255]
            file.seek(0)
            data["content_sha256"] = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)

        document_type = data.get("document_type", "")
        allowed_types = {
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED: {
                "identity",
                "passport",
                "national_id",
                "drivers_license",
            },
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED: {
                "business_registration",
                "tax_id",
                "business_location",
                "business_activity",
            },
        }.get(verification_request.target_level, set())
        if document_type not in allowed_types:
            raise ValidationError(
                {
                    "document_type": "Ce type de justificatif ne correspond pas à la demande."
                }
            )

        return data

    @staticmethod
    def _mime_from_signature(signature: bytes) -> str:
        if signature.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if signature.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if signature.startswith(b"%PDF-"):
            return "application/pdf"
        if len(signature) >= 12 and signature[4:8] == b"ftyp":
            brand = signature[8:12]
            if brand in {b"heic", b"heix", b"hevc", b"hevx"}:
                return "image/heic"
            if brand == b"mif1":
                return "image/heif"
        return ""

    def create(self, validated_data: Dict[str, Any]) -> VerificationDocument:
        """Crée un nouveau document."""
        request = self.context.get("request")
        verification_request = self.context.get("verification_request")

        validated_data["request"] = verification_request
        validated_data["original_filename"] = (
            f"verification-document{os.path.splitext(validated_data['file'].name)[1].lower()}"
        )
        validated_data["is_valid_format"] = True

        document = super().create(validated_data)

        # Log d'audit
        from .models import CertificationAuditLog

        CertificationAuditLog.objects.create(
            user=verification_request.user,
            request=verification_request,
            document=document,
            action=CertificationAuditLog.ActionType.DOCUMENT_UPLOADED,
            actor=verification_request.user,
            details={
                "document_type": document.document_type,
                "file_size": document.file_size,
            },
        )

        return document


class SellerCertificationSerializer(serializers.ModelSerializer):
    """Serializer pour les certifications de vendeur."""

    user_display_name = serializers.CharField(source="user.username", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    granted_by_display = serializers.CharField(
        source="granted_by.username", read_only=True
    )
    is_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = SellerCertification
        fields = [
            "id",
            "user",
            "user_display_name",
            "level",
            "level_display",
            "verification_request",
            "granted_at",
            "expires_at",
            "days_until_expiry",
            "revoked_at",
            "granted_by",
            "granted_by_display",
            "is_active",
        ]
        read_only_fields = fields


class VerificationCriteriaSerializer(serializers.ModelSerializer):
    """Serializer pour les critères de vérification."""

    level_display = serializers.CharField(source="get_level_display", read_only=True)
    badge_name = serializers.CharField(read_only=True)
    requirements = serializers.SerializerMethodField()

    class Meta:
        model = VerificationCriteria
        fields = [
            "id",
            "level",
            "level_display",
            "display_name",
            "badge_name",
            "description",
            "benefits",
            "requires_profile",
            "requires_email_verification",
            "requires_identity_verification",
            "identity_verification_types",
            "requires_business_verification",
            "business_verification_types",
            "requires_transaction_count",
            "requires_account_age_days",
            "requires_minimum_rating",
            "max_cancellation_rate",
            "requires_no_active_disputes",
            "is_automatic",
            "requires_admin_approval",
            "validity_period_days",
            "is_active",
            "requirements",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "badge_name",
            "requirements",
            "created_at",
            "updated_at",
        ]

    def get_requirements(self, obj: VerificationCriteria) -> Dict[str, Any]:
        """Retourne les exigences sous forme de dictionnaire."""
        return obj.get_requirements()


class RiskSignalSerializer(serializers.ModelSerializer):
    """Serializer pour les signaux de risque."""

    user_display_name = serializers.CharField(source="user.username", read_only=True)
    signal_type_display = serializers.CharField(
        source="get_signal_type_display", read_only=True
    )
    severity_display = serializers.CharField(
        source="get_severity_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reviewed_by_display = serializers.CharField(
        source="reviewed_by.username", read_only=True
    )
    is_actionable = serializers.BooleanField(read_only=True)

    class Meta:
        model = RiskSignal
        fields = [
            "id",
            "user",
            "user_display_name",
            "signal_type",
            "signal_type_display",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "evidence",
            "confidence_score",
            "detected_by",
            "reviewed_by",
            "reviewed_by_display",
            "review_notes",
            "action_taken",
            "detected_at",
            "reviewed_at",
            "resolved_at",
            "is_actionable",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "detected_by",
            "detected_at",
            "reviewed_at",
            "resolved_at",
            "is_actionable",
        ]


class UserVerificationStatusSerializer(serializers.Serializer):
    """Serializer pour le statut de vérification d'un utilisateur."""

    user_id = serializers.UUIDField(source="id")
    username = serializers.CharField()
    email = serializers.EmailField()
    seller_type = serializers.CharField(source="get_seller_type_display")
    is_email_verified = serializers.BooleanField()

    # Certifications actives
    certifications = serializers.SerializerMethodField()

    # Demandes en cours
    pending_requests = serializers.SerializerMethodField()
    requests = serializers.SerializerMethodField()

    # Éligibilité aux niveaux
    eligible_levels = serializers.SerializerMethodField()
    current_highest_level = serializers.SerializerMethodField()

    # Métriques pour le niveau 4
    transaction_count = serializers.SerializerMethodField()
    account_age_days = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()

    # Risques détectés
    risk_signals_count = serializers.SerializerMethodField()
    has_high_risk_signals = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "user_id",
            "username",
            "email",
            "seller_type",
            "is_email_verified",
            "certifications",
            "pending_requests",
            "requests",
            "eligible_levels",
            "current_highest_level",
            "transaction_count",
            "account_age_days",
            "average_rating",
            "risk_signals_count",
            "has_high_risk_signals",
        ]

    def get_account_age_days(self, obj) -> int:
        """Calcule l'ancienneté du compte en jours."""
        if hasattr(obj, "date_joined"):
            delta = timezone.now() - obj.date_joined
            return delta.days
        return 0

    def get_certifications(self, obj) -> list:
        active = [
            certification
            for certification in obj.certifications.exclude(
                level__in=[
                    VerificationLevel.LEVEL_0_PROFILE_CREATED,
                    VerificationLevel.LEVEL_1_EMAIL_VERIFIED,
                    VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
                ]
            )
            if certification.is_active
        ]
        return SellerCertificationSerializer(active, many=True).data

    def get_pending_requests(self, obj) -> list:
        active = obj.verification_requests.filter(
            status__in=[
                VerificationRequestStatus.DRAFT,
                VerificationRequestStatus.PENDING,
                VerificationRequestStatus.UNDER_REVIEW,
                VerificationRequestStatus.NEEDS_MORE_INFORMATION,
            ]
        )
        return VerificationRequestSerializer(
            active, many=True, context=self.context
        ).data

    def get_requests(self, obj) -> list:
        recent = obj.verification_requests.all().order_by("-created_at")[:10]
        return VerificationRequestSerializer(
            recent, many=True, context=self.context
        ).data

    def get_transaction_count(self, obj) -> int:
        from .services import VerificationService

        return VerificationService._completed_transaction_count(obj)

    def get_average_rating(self, obj):
        from .services import VerificationService

        return VerificationService._completed_transaction_rating(obj) or 0

    def get_eligible_levels(self, obj) -> list:
        """Détermine les niveaux pour lesquels l'utilisateur est éligible."""
        from .services import VerificationService

        service = VerificationService()
        eligible_levels = service.get_eligible_levels(obj)

        achieved = {VerificationLevel.LEVEL_0_PROFILE_CREATED}
        if obj.is_email_verified:
            achieved.add(VerificationLevel.LEVEL_1_EMAIL_VERIFIED)
        achieved.update(
            certification["level"] for certification in self.get_certifications(obj)
        )
        if VerificationLevel.LEVEL_4_RELIABLE_HISTORY in eligible_levels:
            achieved.add(VerificationLevel.LEVEL_4_RELIABLE_HISTORY)
        if VerificationLevel.LEVEL_4_RELIABLE_HISTORY in eligible_levels:
            achieved.add(VerificationLevel.LEVEL_4_RELIABLE_HISTORY)
        return [
            {
                "level": level,
                "level_display": dict(VerificationLevel.choices).get(level, level),
                "is_achieved": level in achieved,
            }
            for level in eligible_levels
        ]

    def get_current_highest_level(self, obj) -> dict:
        """Retourne le plus haut niveau de certification actif."""
        active_certifications = self.get_certifications(obj)
        level_order = {
            VerificationLevel.LEVEL_0_PROFILE_CREATED: 0,
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED: 1,
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED: 2,
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED: 3,
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY: 4,
        }

        achieved = {VerificationLevel.LEVEL_0_PROFILE_CREATED}
        if obj.is_email_verified:
            achieved.add(VerificationLevel.LEVEL_1_EMAIL_VERIFIED)
        achieved.update(
            certification["level"] for certification in active_certifications
        )
        from .services import VerificationService

        service = VerificationService()
        history = service._get_criteria_by_level().get(
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY
        )
        if history and service._check_level_eligibility(obj, history):
            achieved.add(VerificationLevel.LEVEL_4_RELIABLE_HISTORY)
        highest_level = max(achieved, key=lambda level: level_order.get(level, 0))

        return {
            "level": highest_level,
            "level_display": dict(VerificationLevel.choices).get(highest_level),
            "is_achieved": True,
        }

    def get_risk_signals_count(self, obj) -> int:
        """Compte les signaux de risque actifs."""
        return obj.risk_signals.filter(status__in=["active", "reviewed"]).count()

    def get_has_high_risk_signals(self, obj) -> bool:
        """Vérifie s'il y a des signaux de risque élevés ou critiques."""
        return obj.risk_signals.filter(
            status__in=["active", "reviewed"], severity__in=["high", "critical"]
        ).exists()
