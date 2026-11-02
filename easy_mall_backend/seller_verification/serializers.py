"""
Serializers pour le système de certification des vendeurs.
"""

import os
from typing import Dict, Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

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
            "original_filename",
            "file_size",
            "file_size_mb",
            "mime_type",
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
        if request and request.user.has_perm("seller_verification.view_verificationdocument"):
            # Seuls les administrateurs autorisés peuvent télécharger les documents
            return request.build_absolute_uri(f"/api/seller-verification/documents/{obj.id}/download/")
        return ""
    
    def get_file_size_mb(self, obj: VerificationDocument) -> float:
        """Retourne la taille en Mo avec 2 décimales."""
        return round(obj.file_size / (1024 * 1024), 2)


class VerificationRequestSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes de vérification."""
    
    user_display_name = serializers.CharField(source="user.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    verification_type_display = serializers.CharField(source="get_verification_type_display", read_only=True)
    target_level_display = serializers.CharField(source="get_target_level_display", read_only=True)
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
            "submitted_at",
            "expires_at",
            "days_until_expiry",
            "reviewed_by",
            "reviewed_at",
            "decision_notes",
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
        
        # L'utilisateur ne peut créer des demandes que pour lui-même
        if self.instance is None:  # Création
            data["user"] = request.user
        elif self.instance.user != request.user:
            raise PermissionDenied("Vous ne pouvez modifier que vos propres demandes.")
        
        # Validation spécifique au type de vérification
        verification_type = data.get("verification_type", getattr(self.instance, "verification_type", None))
        target_level = data.get("target_level", getattr(self.instance, "target_level", None))
        
        # Vérification de la cohérence niveau/type
        if verification_type == VerificationType.IDENTITY_DOCUMENT:
            if target_level != VerificationLevel.LEVEL_2_IDENTITY_VERIFIED:
                raise ValidationError({
                    "target_level": "Les documents d'identité sont requis pour le niveau 2 (Identité examinée)."
                })
        
        elif verification_type == VerificationType.BUSINESS_REGISTRATION:
            if target_level != VerificationLevel.LEVEL_3_BUSINESS_VERIFIED:
                raise ValidationError({
                    "target_level": "Les enregistrements commerciaux sont requis pour le niveau 3 (Commerçant professionnel vérifié)."
                })
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> VerificationRequest:
        """Crée une nouvelle demande."""
        request = self.context.get("request")
        if not request:
            raise PermissionDenied("Authentification requise.")
        
        validated_data["user"] = request.user
        validated_data["status"] = VerificationRequestStatus.DRAFT
        
        # Vérifier si l'utilisateur a déjà une certification pour ce niveau
        existing_certification = SellerCertification.objects.filter(
            user=request.user,
            level=validated_data["target_level"],
            revoked_at__isnull=True
        ).first()
        
        if existing_certification:
            raise ValidationError({
                "target_level": f"Vous avez déjà une certification active pour le niveau {existing_certification.get_level_display()}."
            })
        
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
        
        if verification_request.status != VerificationRequestStatus.DRAFT:
            raise ValidationError("Seules les demandes brouillons peuvent être soumises.")
        
        # Vérifier qu'il y a au moins un document
        if not verification_request.documents.exists():
            raise ValidationError("Au moins un document doit être téléchargé avant de soumettre la demande.")
        
        # Vérifier que tous les documents ont un format valide
        invalid_docs = verification_request.documents.filter(is_valid_format=False)
        if invalid_docs.exists():
            raise ValidationError("Tous les documents doivent avoir un format valide avant soumission.")
        
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
            details={"status": verification_request.status}
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
            raise PermissionDenied("Vous ne pouvez ajouter des documents qu'à vos propres demandes.")
        
        if verification_request.status != VerificationRequestStatus.DRAFT:
            raise ValidationError("Les documents ne peuvent être ajoutés qu'aux demandes brouillons.")
        
        # Validation du fichier
        file = data.get("file")
        if file:
            # Vérification de la taille
            max_size = VerificationDocument.MAX_FILE_SIZE
            if file.size > max_size:
                raise ValidationError({
                    "file": f"Le fichier est trop volumineux. Taille maximale : {max_size // (1024 * 1024)} Mo"
                })
            
            # Vérification de l'extension
            ext = os.path.splitext(file.name)[1].lower()
            allowed_extensions = VerificationDocument.ALLOWED_EXTENSIONS
            if ext not in allowed_extensions:
                raise ValidationError({
                    "file": f"Extension de fichier non autorisée. Extensions autorisées : {', '.join(allowed_extensions)}"
                })
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> VerificationDocument:
        """Crée un nouveau document."""
        request = self.context.get("request")
        verification_request = self.context.get("verification_request")
        
        validated_data["request"] = verification_request
        validated_data["original_filename"] = validated_data["file"].name
        
        # Validation automatique du format
        validated_data["is_valid_format"] = True  # Serait déterminé par une tâche asynchrone
        
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
                "original_filename": document.original_filename,
                "file_size": document.file_size,
            }
        )
        
        return document


class SellerCertificationSerializer(serializers.ModelSerializer):
    """Serializer pour les certifications de vendeur."""
    
    user_display_name = serializers.CharField(source="user.username", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    granted_by_display = serializers.CharField(source="granted_by.username", read_only=True)
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
            "revoked_by",
            "revocation_reason",
            "notes",
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
    signal_type_display = serializers.CharField(source="get_signal_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reviewed_by_display = serializers.CharField(source="reviewed_by.username", read_only=True)
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
    certifications = SellerCertificationSerializer(many=True, source="active_certifications")
    
    # Demandes en cours
    pending_requests = VerificationRequestSerializer(many=True, source="active_verification_requests")
    
    # Éligibilité aux niveaux
    eligible_levels = serializers.SerializerMethodField()
    current_highest_level = serializers.SerializerMethodField()
    
    # Métriques pour le niveau 4
    transaction_count = serializers.IntegerField(source="total_sales")
    account_age_days = serializers.SerializerMethodField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    
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
    
    def get_eligible_levels(self, obj) -> list:
        """Détermine les niveaux pour lesquels l'utilisateur est éligible."""
        from .services import VerificationService
        
        service = VerificationService()
        eligible_levels = service.get_eligible_levels(obj)
        
        return [
            {
                "level": level,
                "level_display": dict(VerificationLevel.choices).get(level, level),
                "is_achieved": level in [cert.level for cert in obj.certifications.filter(revoked_at__isnull=True)]
            }
            for level in eligible_levels
        ]
    
    def get_current_highest_level(self, obj) -> dict:
        """Retourne le plus haut niveau de certification actif."""
        active_certifications = obj.certifications.filter(revoked_at__isnull=True)
        
        if not active_certifications.exists():
            return {
                "level": VerificationLevel.LEVEL_0_PROFILE_CREATED,
                "level_display": dict(VerificationLevel.choices).get(VerificationLevel.LEVEL_0_PROFILE_CREATED),
                "is_achieved": True,
            }
        
        # Trouver le niveau le plus élevé
        level_order = {
            VerificationLevel.LEVEL_0_PROFILE_CREATED: 0,
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED: 1,
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED: 2,
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED: 3,
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY: 4,
        }
        
        highest_cert = max(
            active_certifications,
            key=lambda c: level_order.get(c.level, 0)
        )
        
        return {
            "level": highest_cert.level,
            "level_display": highest_cert.get_level_display(),
            "is_achieved": True,
        }
    
    def get_risk_signals_count(self, obj) -> int:
        """Compte les signaux de risque actifs."""
        return obj.risk_signals.filter(
            status__in=["active", "reviewed"]
        ).count()
    
    def get_has_high_risk_signals(self, obj) -> bool:
        """Vérifie s'il y a des signaux de risque élevés ou critiques."""
        return obj.risk_signals.filter(
            status__in=["active", "reviewed"],
            severity__in=["high", "critical"]
        ).exists()