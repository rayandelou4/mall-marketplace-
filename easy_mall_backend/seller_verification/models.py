"""
Modèles pour le système de certification des vendeurs.

Ce module gère les demandes de vérification d'identité, les documents soumis,
les décisions administratives et les niveaux de certification obtenus.
"""

import uuid
import os
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .storage import private_verification_storage


class VerificationLevel(models.TextChoices):
    """Niveaux de certification des vendeurs."""

    LEVEL_0_PROFILE_CREATED = "level_0", _("Profil créé")
    LEVEL_1_EMAIL_VERIFIED = "level_1", _("E-mail vérifié")
    LEVEL_2_IDENTITY_VERIFIED = "level_2", _("Identité examinée")
    LEVEL_3_BUSINESS_VERIFIED = "level_3", _("Commerçant professionnel vérifié")
    LEVEL_4_RELIABLE_HISTORY = "level_4", _("Historique commercial fiable")


class VerificationRequestStatus(models.TextChoices):
    """Statuts d'une demande de vérification."""

    DRAFT = "draft", _("Brouillon")
    PENDING = "pending", _("En attente")
    NEEDS_MORE_INFORMATION = "needs_more_info", _(
        "Informations complémentaires demandées"
    )
    UNDER_REVIEW = "under_review", _("En cours d'examen")
    APPROVED = "approved", _("Approuvé")
    REJECTED = "rejected", _("Refusé")
    EXPIRED = "expired", _("Expiré")
    CANCELLED = "cancelled", _("Annulé")


class VerificationType(models.TextChoices):
    """Types de vérification disponibles."""

    IDENTITY_DOCUMENT = "identity", _("Document d'identité")
    BUSINESS_REGISTRATION = "business_registration", _("Enregistrement commercial")
    BUSINESS_LOCATION = "business_location", _("Localisation commerciale")
    BUSINESS_ACTIVITY_PROOF = "business_activity", _("Preuve d'activité commerciale")
    LIVE_CHALLENGE = "live_challenge", _("Défi de vérification en direct")


class SellerCertification(models.Model):
    """
    Certification d'un vendeur à un niveau spécifique.

    Chaque niveau doit être certifié séparément et peut expirer si nécessaire.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certifications",
        verbose_name=_("utilisateur"),
    )

    level = models.CharField(
        max_length=20,
        choices=VerificationLevel.choices,
        verbose_name=_("niveau de certification"),
    )

    # Référence à la demande qui a conduit à cette certification
    verification_request = models.OneToOneField(
        "VerificationRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resulting_certification",
        verbose_name=_("demande de vérification"),
    )

    # Dates importantes
    granted_at = models.DateTimeField(
        default=timezone.now, verbose_name=_("date d'attribution")
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("date d'expiration")
    )
    revoked_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("date de révocation")
    )

    # Informations sur la décision
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_certifications",
        verbose_name=_("attribuée par"),
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_certifications",
        verbose_name=_("révoquée par"),
    )
    revocation_reason = models.TextField(
        blank=True, verbose_name=_("motif de révocation")
    )

    notes = models.TextField(blank=True, verbose_name=_("notes internes"))

    class Meta:
        db_table = "seller_certifications"
        verbose_name = _("certification de vendeur")
        verbose_name_plural = _("certifications de vendeurs")
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "level"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_certification_per_level",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "level", "revoked_at"],
                name="sv_cert_user_level_rev_idx",
            ),
            models.Index(fields=["expires_at"], name="sv_cert_expires_idx"),
            models.Index(fields=["granted_at"], name="sv_cert_granted_idx"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_level_display()}"

    @property
    def is_active(self) -> bool:
        """Vérifie si la certification est active (non révoquée et non expirée)."""
        if self.revoked_at is not None:
            return False

        if self.expires_at is not None and timezone.now() > self.expires_at:
            return False

        return True

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Nombre de jours jusqu'à l'expiration (None si pas d'expiration)."""
        if self.expires_at is None:
            return None

        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def revoke(self, user: settings.AUTH_USER_MODEL, reason: str = "") -> None:
        """Révoque la certification."""
        if self.revoked_at is not None:
            raise ValidationError(_("Cette certification est déjà révoquée."))

        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.revocation_reason = reason
        self.save()


class VerificationRequest(models.Model):
    """
    Demande de vérification soumise par un vendeur.

    Chaque demande correspond à un type spécifique (identité, commerce, etc.)
    et peut contenir plusieurs documents.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_requests",
        verbose_name=_("demandeur"),
    )

    verification_type = models.CharField(
        max_length=30,
        choices=VerificationType.choices,
        verbose_name=_("type de vérification"),
    )

    target_level = models.CharField(
        max_length=20, choices=VerificationLevel.choices, verbose_name=_("niveau ciblé")
    )

    status = models.CharField(
        max_length=20,
        choices=VerificationRequestStatus.choices,
        default=VerificationRequestStatus.DRAFT,
        verbose_name=_("statut"),
    )

    # Informations contextuelles
    description = models.TextField(
        blank=True, verbose_name=_("description de la demande")
    )

    # Dates importantes
    submitted_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("date de soumission")
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("date d'expiration")
    )

    # Décision administrative
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verification_requests",
        verbose_name=_("examiné par"),
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("date d'examen")
    )
    decision_notes = models.TextField(blank=True, verbose_name=_("notes de décision"))
    seller_message = models.TextField(
        blank=True, verbose_name=_("message communiqué au vendeur")
    )
    rejection_reason = models.TextField(blank=True, verbose_name=_("motif de refus"))

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "verification_requests"
        verbose_name = _("demande de vérification")
        verbose_name_plural = _("demandes de vérification")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="sv_request_user_status_idx"),
            models.Index(
                fields=["status", "submitted_at"], name="sv_request_status_sub_idx"
            ),
            models.Index(fields=["expires_at"], name="sv_request_expires_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "verification_type"],
                condition=models.Q(
                    status__in=[
                        VerificationRequestStatus.DRAFT,
                        VerificationRequestStatus.PENDING,
                        VerificationRequestStatus.UNDER_REVIEW,
                        VerificationRequestStatus.NEEDS_MORE_INFORMATION,
                    ]
                ),
                name="unique_open_verification_request_per_type",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_verification_type_display()} - {self.get_status_display()}"

    def clean(self):
        """Validation supplémentaire."""
        if self.submitted_at and not self.expires_at:
            # Les demandes soumises expirent après 30 jours par défaut
            self.expires_at = self.submitted_at + timedelta(days=30)

        # Un vendeur ne peut pas avoir deux demandes actives du même type
        if self.status in [
            VerificationRequestStatus.DRAFT,
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.UNDER_REVIEW,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        ]:
            existing_active = VerificationRequest.objects.filter(
                user=self.user,
                verification_type=self.verification_type,
                status__in=[
                    VerificationRequestStatus.DRAFT,
                    VerificationRequestStatus.PENDING,
                    VerificationRequestStatus.UNDER_REVIEW,
                    VerificationRequestStatus.NEEDS_MORE_INFORMATION,
                ],
            ).exclude(id=self.id)

            if existing_active.exists():
                raise ValidationError(
                    _(
                        "Une demande active du même type existe déjà pour cet utilisateur."
                    )
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Vérifie si la demande est active (non terminée, non expirée)."""
        if self.status in [
            VerificationRequestStatus.APPROVED,
            VerificationRequestStatus.REJECTED,
            VerificationRequestStatus.EXPIRED,
            VerificationRequestStatus.CANCELLED,
        ]:
            return False

        if self.expires_at and timezone.now() > self.expires_at:
            return False

        return True

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Nombre de jours jusqu'à l'expiration."""
        if not self.expires_at:
            return None

        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def submit(self) -> None:
        """Soumet la demande (passe de DRAFT à PENDING)."""
        if self.status not in {
            VerificationRequestStatus.DRAFT,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        }:
            raise ValidationError(
                _("Cette demande ne peut pas être soumise dans son état actuel.")
            )

        self.status = VerificationRequestStatus.PENDING
        self.seller_message = ""
        self.submitted_at = timezone.now()
        self.expires_at = self.submitted_at + timedelta(days=30)
        self.save()

    def cancel(self) -> None:
        """Annule la demande."""
        if self.status not in [
            VerificationRequestStatus.DRAFT,
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        ]:
            raise ValidationError(
                _("Cette demande ne peut pas être annulée dans son état actuel.")
            )

        self.status = VerificationRequestStatus.CANCELLED
        self.save()
        self.documents.update(retention_expires_at=timezone.now() + timedelta(days=90))
        self.documents.update(retention_expires_at=timezone.now() + timedelta(days=90))


def verification_document_path(instance: "VerificationDocument", filename: str) -> str:
    """Génère un chemin sécurisé pour le stockage des documents de vérification."""
    # Utilise un nom de fichier généré par le serveur pour éviter les attaques par chemin
    ext = os.path.splitext(filename)[1]
    safe_filename = f"{uuid.uuid4()}{ext}"

    # Structure: verification_documents/{user_id}/{request_id}/{filename}
    return f"verification_documents/{instance.request.user.id}/{instance.request.id}/{safe_filename}"


class VerificationDocument(models.Model):
    """
    Document soumis dans le cadre d'une demande de vérification.

    Les documents sont stockés de manière sécurisée et ne sont accessibles
    qu'aux administrateurs autorisés.
    """

    ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "pdf", "heic", "heif"]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("demande de vérification"),
    )

    document_type = models.CharField(max_length=50, verbose_name=_("type de document"))

    file = models.FileField(
        upload_to=verification_document_path,
        storage=private_verification_storage,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)],
        verbose_name=_("fichier"),
    )

    # Métadonnées du fichier
    original_filename = models.CharField(
        max_length=255, verbose_name=_("nom de fichier original")
    )
    file_size = models.PositiveIntegerField(
        verbose_name=_("taille du fichier (octets)")
    )
    mime_type = models.CharField(max_length=100, verbose_name=_("type MIME"))

    # Informations descriptives
    description = models.TextField(blank=True, verbose_name=_("description"))

    # Validation automatique
    is_valid_format = models.BooleanField(
        default=False, verbose_name=_("format valide")
    )
    validation_errors = models.JSONField(
        default=list, blank=True, verbose_name=_("erreurs de validation")
    )

    # Dates
    uploaded_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    retention_expires_at = models.DateTimeField(null=True, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        db_table = "verification_documents"
        verbose_name = _("document de vérification")
        verbose_name_plural = _("documents de vérification")
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.document_type} - {self.original_filename}"

    def clean(self):
        """Validation du fichier."""
        if self.file and self.file.size > self.MAX_FILE_SIZE:
            raise ValidationError(
                _("Le fichier est trop volumineux. Taille maximale : %(max_size)s Mo")
                % {"max_size": self.MAX_FILE_SIZE // (1024 * 1024)}
            )

    def save(self, *args, **kwargs):
        """Enregistre les métadonnées du fichier."""
        if self.file:
            if not self.original_filename:
                extension = os.path.splitext(self.file.name)[1].lower()
                self.original_filename = f"verification-document{extension}"
            self.file_size = self.file.size

            # Détection basique du type MIME
            ext = os.path.splitext(self.file.name)[1].lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".pdf": "application/pdf",
                ".heic": "image/heic",
                ".heif": "image/heif",
            }
            if not self.mime_type:
                self.mime_type = mime_map.get(ext, "application/octet-stream")

        super().save(*args, **kwargs)


@receiver(post_delete, sender=VerificationDocument)
def delete_private_verification_file(sender, instance, **kwargs):
    if not instance.file:
        return
    storage = instance.file.storage
    file_name = instance.file.name
    if file_name:
        transaction.on_commit(lambda: storage.delete(file_name))


class CertificationAuditLog(models.Model):
    """
    Journal d'audit pour tracer toutes les actions liées à la certification.

    Utilisé pour la traçabilité et la conformité.
    """

    class ActionType(models.TextChoices):
        REQUEST_CREATED = "request_created", _("Demande créée")
        REQUEST_SUBMITTED = "request_submitted", _("Demande soumise")
        REQUEST_REVIEWED = "request_reviewed", _("Demande examinée")
        REQUEST_APPROVED = "request_approved", _("Demande approuvée")
        REQUEST_REJECTED = "request_rejected", _("Demande refusée")
        REQUEST_CANCELLED = "request_cancelled", _("Demande annulée")
        REQUEST_EXPIRED = "request_expired", _("Demande expirée")

        CERTIFICATION_GRANTED = "certification_granted", _("Certification attribuée")
        CERTIFICATION_REVOKED = "certification_revoked", _("Certification révoquée")
        CERTIFICATION_EXPIRED = "certification_expired", _("Certification expirée")

        DOCUMENT_UPLOADED = "document_uploaded", _("Document téléchargé")
        DOCUMENT_VALIDATED = "document_validated", _("Document validé")
        DOCUMENT_REJECTED = "document_rejected", _("Document rejeté")

        ADMIN_ACTION = "admin_action", _("Action administrative")
        STATUS_CHANGE = "status_change", _("Changement de statut")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Référence à l'entité concernée
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certification_audit_logs",
        verbose_name=_("utilisateur concerné"),
    )

    request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("demande concernée"),
    )

    certification = models.ForeignKey(
        SellerCertification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("certification concernée"),
    )

    document = models.ForeignKey(
        VerificationDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("document concerné"),
    )

    # Informations sur l'action
    action = models.CharField(
        max_length=30, choices=ActionType.choices, verbose_name=_("type d'action")
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_certification_actions",
        verbose_name=_("acteur"),
    )

    # Détails de l'action
    details = models.JSONField(
        default=dict, blank=True, verbose_name=_("détails de l'action")
    )

    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name=_("adresse IP")
    )

    user_agent = models.TextField(blank=True, verbose_name=_("agent utilisateur"))

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "certification_audit_logs"
        verbose_name = _("journal d'audit de certification")
        verbose_name_plural = _("journaux d'audit de certification")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "created_at"], name="sv_audit_user_created_idx"
            ),
            models.Index(
                fields=["action", "created_at"], name="sv_audit_action_created_idx"
            ),
            models.Index(
                fields=["actor", "created_at"], name="sv_audit_actor_created_idx"
            ),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.user.username} - {self.created_at}"


class VerificationCriteria(models.Model):
    """
    Critères configurables pour chaque niveau de vérification.

    Permet de définir les conditions requises pour obtenir chaque niveau.
    """

    level = models.CharField(
        max_length=20,
        choices=VerificationLevel.choices,
        unique=True,
        verbose_name=_("niveau de certification"),
    )

    # Critères pour le niveau 0 (profil créé)
    requires_profile = models.BooleanField(
        default=True, verbose_name=_("profil créé requis")
    )

    # Critères pour le niveau 1 (email vérifié)
    requires_email_verification = models.BooleanField(
        default=False, verbose_name=_("email vérifié requis")
    )

    # Critères pour le niveau 2 (identité examinée)
    requires_identity_verification = models.BooleanField(
        default=False, verbose_name=_("vérification d'identité requise")
    )
    identity_verification_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("types de documents d'identité acceptés"),
    )

    # Critères pour le niveau 3 (commerce vérifié)
    requires_business_verification = models.BooleanField(
        default=False, verbose_name=_("vérification commerciale requise")
    )
    business_verification_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("types de preuves commerciales acceptées"),
    )

    # Critères pour le niveau 4 (historique fiable)
    requires_transaction_count = models.PositiveIntegerField(
        default=0, verbose_name=_("nombre minimum de transactions")
    )
    requires_account_age_days = models.PositiveIntegerField(
        default=0, verbose_name=_("ancienneté minimum du compte (jours)")
    )
    requires_minimum_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("note minimum"),
    )
    max_cancellation_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("taux d'annulation maximum (%)"),
    )
    requires_no_active_disputes = models.BooleanField(
        default=False, verbose_name=_("aucun litige actif requis")
    )

    # Paramètres généraux
    is_automatic = models.BooleanField(
        default=False, verbose_name=_("attribution automatique")
    )
    requires_admin_approval = models.BooleanField(
        default=True, verbose_name=_("approbation administrative requise")
    )
    validity_period_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("période de validité (jours)")
    )
    display_name = models.CharField(
        max_length=100, blank=True, verbose_name=_("nom d'affichage")
    )
    description = models.TextField(blank=True, verbose_name=_("description"))
    benefits = models.JSONField(default=list, blank=True, verbose_name=_("avantages"))

    # Métadonnées
    is_active = models.BooleanField(default=True, verbose_name=_("actif"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "verification_criteria"
        verbose_name = _("critères de vérification")
        verbose_name_plural = _("critères de vérification")

    def __str__(self):
        return f"{self.get_level_display()} - Critères"

    @property
    def badge_name(self) -> str:
        """Nom du badge à afficher."""
        if self.display_name:
            return self.display_name

        level_display = self.get_level_display()
        return f"Certifié {level_display}"

    def get_requirements(self) -> dict:
        """Retourne les exigences sous forme de dictionnaire."""
        return {
            "requires_profile": self.requires_profile,
            "requires_email_verification": self.requires_email_verification,
            "requires_identity_verification": self.requires_identity_verification,
            "requires_business_verification": self.requires_business_verification,
            "requires_transaction_count": self.requires_transaction_count,
            "requires_account_age_days": self.requires_account_age_days,
            "requires_minimum_rating": float(self.requires_minimum_rating),
            "max_cancellation_rate": float(self.max_cancellation_rate),
            "requires_no_active_disputes": self.requires_no_active_disputes,
            "is_automatic": self.is_automatic,
            "requires_admin_approval": self.requires_admin_approval,
            "validity_period_days": self.validity_period_days,
        }


class RiskSignal(models.Model):
    """
    Signal de risque détecté pour un utilisateur.

    Utilisé pour identifier les comptes nécessitant une vérification supplémentaire
    ou un examen approfondi.
    """

    class SignalType(models.TextChoices):
        MULTIPLE_ACCOUNTS = "multiple_accounts", _("Multiples comptes")
        REPEATED_VERIFICATION_REQUESTS = "repeated_requests", _(
            "Demandes de vérification répétées"
        )
        FREQUENT_PROFILE_CHANGES = "frequent_changes", _(
            "Changements fréquents de profil"
        )
        DUPLICATE_DOCUMENTS = "duplicate_documents", _(
            "Documents identiques sur plusieurs comptes"
        )
        SUSPICIOUS_BEHAVIOR = "suspicious_behavior", _("Comportement suspect")
        ABNORMAL_TRANSACTIONS = "abnormal_transactions", _("Transactions anormales")
        HIGH_RISK_LOCATION = "high_risk_location", _("Localisation à risque")
        OTHER = "other", _("Autre")

    class Severity(models.TextChoices):
        LOW = "low", _("Faible")
        MEDIUM = "medium", _("Moyen")
        HIGH = "high", _("Élevé")
        CRITICAL = "critical", _("Critique")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Actif")
        REVIEWED = "reviewed", _("Examiné")
        RESOLVED = "resolved", _("Résolu")
        FALSE_POSITIVE = "false_positive", _("Faux positif")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="risk_signals",
        verbose_name=_("utilisateur"),
    )

    signal_type = models.CharField(
        max_length=30, choices=SignalType.choices, verbose_name=_("type de signal")
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        verbose_name=_("sévérité"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("statut"),
    )

    # Détails du signal
    description = models.TextField(verbose_name=_("description"))
    evidence = models.JSONField(default=dict, blank=True, verbose_name=_("preuves"))
    confidence_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.5,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name=_("score de confiance"),
    )

    # Gestion du signal
    detected_by = models.CharField(
        max_length=100, default="system", verbose_name=_("détecté par")
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_risk_signals",
        verbose_name=_("examiné par"),
    )
    review_notes = models.TextField(blank=True, verbose_name=_("notes d'examen"))
    action_taken = models.TextField(blank=True, verbose_name=_("action entreprise"))

    # Dates
    detected_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "risk_signals"
        verbose_name = _("signal de risque")
        verbose_name_plural = _("signaux de risque")
        ordering = ["-detected_at"]
        indexes = [
            models.Index(
                fields=["user", "status", "severity"],
                name="sv_risk_user_status_sev_idx",
            ),
            models.Index(
                fields=["signal_type", "status"], name="sv_risk_type_status_idx"
            ),
        ]

    def __str__(self):
        return f"{self.get_signal_type_display()} - {self.user.username} - {self.get_severity_display()}"

    @property
    def is_actionable(self) -> bool:
        """Indique si le signal nécessite une action."""
        return self.status == RiskSignal.Status.ACTIVE and self.severity in [
            RiskSignal.Severity.HIGH,
            RiskSignal.Severity.CRITICAL,
        ]

    def mark_as_reviewed(self, user: settings.AUTH_USER_MODEL, notes: str = "") -> None:
        """Marque le signal comme examiné."""
        self.status = RiskSignal.Status.REVIEWED
        self.reviewed_by = user
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()

    def mark_as_resolved(self, action_taken: str = "") -> None:
        """Marque le signal comme résolu."""
        self.status = RiskSignal.Status.RESOLVED
        self.action_taken = action_taken
        self.resolved_at = timezone.now()
        self.save()
