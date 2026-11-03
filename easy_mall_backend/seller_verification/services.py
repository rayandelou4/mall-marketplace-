"""
Services métier pour le système de certification des vendeurs.

Contient la logique de vérification, le calcul d'éligibilité, la détection
de risque et les opérations automatiques.
"""

import hashlib
import json
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Avg, F
from django.utils import timezone

from accounts.models import User
from orders.models import Order, OrderItem
from moderation.models import Dispute
from reviews.models import Review

from .models import (
    SellerCertification,
    VerificationRequest,
    VerificationCriteria,
    RiskSignal,
    VerificationLevel,
    VerificationRequestStatus,
    RiskSignal as RiskSignalModel,
)


class VerificationService:
    """Service principal pour la gestion des certifications."""

    def __init__(self):
        self._criteria_cache = {}

    def get_eligible_levels(self, user: User) -> List[str]:
        """
        Détermine les niveaux de certification pour lesquels l'utilisateur est éligible.

        Args:
            user: L'utilisateur à vérifier

        Returns:
            Liste des niveaux éligibles (ex: ["level_0", "level_1", "level_2"])
        """
        eligible_levels = []

        # Charger les critères depuis la base de données
        criteria_by_level = self._get_criteria_by_level()

        for level, criteria in criteria_by_level.items():
            if self._check_level_eligibility(user, criteria, exclude_target_proof=True):
                eligible_levels.append(level)

        return eligible_levels

    def _get_criteria_by_level(self) -> Dict[str, VerificationCriteria]:
        """Charge les critères de vérification avec cache."""
        if not self._criteria_cache:
            self._criteria_cache = {
                criteria.level: criteria
                for criteria in VerificationCriteria.objects.filter(is_active=True)
            }

        # Critères par défaut si non configurés
        default_levels = set(dict(VerificationLevel.choices).keys())
        configured_levels = set(self._criteria_cache.keys())

        for level in default_levels - configured_levels:
            self._criteria_cache[level] = self._create_default_criteria(level)

        return self._criteria_cache

    def _create_default_criteria(self, level: str) -> VerificationCriteria:
        """Crée des critères par défaut pour un niveau."""
        defaults = {
            VerificationLevel.LEVEL_0_PROFILE_CREATED: {
                "requires_profile": True,
                "requires_email_verification": False,
                "is_automatic": True,
                "requires_admin_approval": False,
                "display_name": "Profil créé",
                "description": "Vous avez créé votre profil sur la plateforme.",
            },
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED: {
                "requires_profile": True,
                "requires_email_verification": True,
                "is_automatic": True,
                "requires_admin_approval": False,
                "display_name": "E-mail vérifié",
                "description": "Vous avez confirmé votre adresse e-mail.",
            },
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED: {
                "requires_profile": True,
                "requires_email_verification": True,
                "requires_identity_verification": True,
                "identity_verification_types": [
                    "identity",
                    "passport",
                    "drivers_license",
                ],
                "is_automatic": False,
                "requires_admin_approval": True,
                "validity_period_days": 365,
                "display_name": "Identité examinée",
                "description": "Votre identité a été vérifiée manuellement par notre équipe.",
            },
            VerificationLevel.LEVEL_3_BUSINESS_VERIFIED: {
                "requires_profile": True,
                "requires_email_verification": True,
                "requires_business_verification": True,
                "business_verification_types": [
                    "business_registration",
                    "tax_id",
                    "business_location",
                ],
                "is_automatic": False,
                "requires_admin_approval": True,
                "requires_no_active_disputes": True,
                "validity_period_days": 365,
                "display_name": "Commerçant professionnel vérifié",
                "description": "Votre activité commerciale a été vérifiée.",
            },
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY: {
                "requires_profile": True,
                "requires_email_verification": True,
                "requires_transaction_count": 10,
                "requires_account_age_days": 90,
                "requires_minimum_rating": 4.0,
                "max_cancellation_rate": 10.0,
                "requires_no_active_disputes": False,
                "is_automatic": True,
                "requires_admin_approval": False,
                "validity_period_days": 180,
                "display_name": "Historique commercial fiable",
                "description": "Vous avez démontré une fiabilité commerciale sur la plateforme.",
            },
        }

        level_defaults = defaults.get(level, {})

        return VerificationCriteria(level=level, **level_defaults)

    def _check_level_eligibility(
        self,
        user: User,
        criteria: VerificationCriteria,
        exclude_target_proof: bool = False,
    ) -> bool:
        """Vérifie si un utilisateur remplit les critères pour un niveau."""
        # Niveau 0 : toujours éligible si compte actif
        if not user.is_active:
            return False

        # 1. Profil requis
        if criteria.requires_profile and not self._has_complete_profile(user):
            return False

        # 2. Email vérifié requis
        if criteria.requires_email_verification and not user.is_email_verified:
            return False

        # 3. Vérification d'identité requise
        if criteria.requires_identity_verification and not (
            exclude_target_proof
            and criteria.level == VerificationLevel.LEVEL_2_IDENTITY_VERIFIED
        ):
            if not self._has_approved_identity_verification(user):
                return False

        # 4. Vérification commerciale requise
        if criteria.requires_business_verification:
            if user.seller_type != User.SellerType.PROFESSIONAL:
                return False
            if not (
                exclude_target_proof
                and criteria.level == VerificationLevel.LEVEL_3_BUSINESS_VERIFIED
            ) and not self._has_approved_business_verification(user):
                return False

        # 5. Critères de réputation (niveau 4)
        if criteria.requires_transaction_count > 0:
            if (
                self._completed_transaction_count(user)
                < criteria.requires_transaction_count
            ):
                return False

        if criteria.requires_account_age_days > 0:
            account_age = (timezone.now() - user.date_joined).days
            if account_age < criteria.requires_account_age_days:
                return False

        if criteria.requires_minimum_rating > 0:
            rating = self._completed_transaction_rating(user)
            if rating is None or rating < float(criteria.requires_minimum_rating):
                return False

        if criteria.max_cancellation_rate < 100:
            cancellation_rate = self._calculate_cancellation_rate(user)
            if cancellation_rate > float(criteria.max_cancellation_rate):
                return False

        if criteria.requires_no_active_disputes:
            if self._has_active_disputes(user):
                return False

        return True

    def _has_complete_profile(self, user: User) -> bool:
        """Le niveau 0 atteste uniquement l'existence d'un compte actif."""
        return bool(user.pk and user.is_active)

    def _has_approved_identity_verification(self, user: User) -> bool:
        """Vérifie si l'utilisateur a une vérification d'identité approuvée."""
        return (
            SellerCertification.objects.filter(
                user=user,
                level=VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
                revoked_at__isnull=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .exists()
        )

    def _has_approved_business_verification(self, user: User) -> bool:
        """Vérifie si l'utilisateur a une vérification commerciale approuvée."""
        return (
            SellerCertification.objects.filter(
                user=user,
                level=VerificationLevel.LEVEL_3_BUSINESS_VERIFIED,
                revoked_at__isnull=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .exists()
        )

    def _calculate_cancellation_rate(self, user: User) -> float:
        """Calcule le taux par commande vendeur résolue, hors remboursements."""
        seller_orders = Order.objects.filter(
            items__seller=user,
            status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED],
        ).distinct()
        total_resolved = seller_orders.count()
        if not total_resolved:
            return 0.0

        cancelled_sales = seller_orders.filter(status=Order.Status.CANCELLED).count()
        return cancelled_sales / total_resolved * 100

    @staticmethod
    def _completed_transaction_count(user: User) -> int:
        return (
            OrderItem.objects.filter(
                seller=user,
                order__status=Order.Status.DELIVERED,
            )
            .values("order_id")
            .distinct()
            .count()
        )

    @staticmethod
    def _completed_transaction_rating(user: User) -> Optional[float]:
        result = Review.objects.filter(
            reviewed_user=user,
            order__status=Order.Status.DELIVERED,
            moderation_status=Review.ModerationStatus.APPROVED,
        ).aggregate(rating=Avg("rating"))["rating"]
        return float(result) if result is not None else None

    def _has_active_disputes(self, user: User) -> bool:
        """Vérifie si l'utilisateur a des litiges actifs."""
        return Dispute.objects.filter(
            Q(seller=user) | Q(raised_by=user),
            status__in=["open", "under_review", "waiting_seller", "waiting_buyer"],
        ).exists()

    def grant_certification(
        self,
        user: User,
        level: str,
        granted_by: Optional[User] = None,
        verification_request: Optional[VerificationRequest] = None,
        notes: str = "",
    ) -> SellerCertification:
        """
        Attribue une certification à un utilisateur.

        Args:
            user: L'utilisateur à certifier
            level: Le niveau de certification
            granted_by: L'administrateur qui attribue (None pour automatique)
            verification_request: La demande liée (optionnel)
            notes: Notes internes

        Returns:
            La certification créée
        """
        if level in {
            VerificationLevel.LEVEL_0_PROFILE_CREATED,
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED,
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
        }:
            raise ValueError(
                "Ce niveau est dérivé dynamiquement et ne peut pas être persisté."
            )

        with transaction.atomic():
            # Vérifier l'éligibilité
            criteria = self._get_criteria_by_level().get(level)
            if not criteria:
                raise ValueError(f"Critères non trouvés pour le niveau {level}")

            if not self._check_level_eligibility(
                user, criteria, exclude_target_proof=True
            ):
                raise ValueError(
                    f"L'utilisateur n'est pas éligible pour le niveau {level}"
                )

            # Révoquer toute certification existante du même niveau
            SellerCertification.objects.filter(
                user=user, level=level, revoked_at__isnull=True
            ).update(
                revoked_at=timezone.now(),
                revoked_by=granted_by,
                revocation_reason="Remplacée par une nouvelle certification",
            )

            # Calculer la date d'expiration
            expires_at = None
            if criteria.validity_period_days:
                expires_at = timezone.now() + timedelta(
                    days=criteria.validity_period_days
                )

            # Créer la nouvelle certification
            certification = SellerCertification.objects.create(
                user=user,
                level=level,
                verification_request=verification_request,
                granted_by=granted_by,
                expires_at=expires_at,
                notes=notes,
            )

            # Journal d'audit
            from .models import CertificationAuditLog

            CertificationAuditLog.objects.create(
                user=user,
                request=verification_request,
                certification=certification,
                action=CertificationAuditLog.ActionType.CERTIFICATION_GRANTED,
                actor=granted_by or user,
                details={
                    "level": level,
                    "level_display": dict(VerificationLevel.choices).get(level),
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )

            return certification

    def revoke_certification(
        self, certification: SellerCertification, revoked_by: User, reason: str
    ) -> None:
        """
        Révoque une certification.

        Args:
            certification: La certification à révoquer
            revoked_by: L'administrateur qui révoque
            reason: Motif de révocation
        """
        with transaction.atomic():
            certification.revoke(revoked_by, reason)

            # Journal d'audit
            from .models import CertificationAuditLog

            CertificationAuditLog.objects.create(
                user=certification.user,
                certification=certification,
                action=CertificationAuditLog.ActionType.CERTIFICATION_REVOKED,
                actor=revoked_by,
                details={
                    "level": certification.level,
                    "reason": reason,
                },
            )

    def check_for_expired_certifications(self) -> List[SellerCertification]:
        """
        Vérifie les certifications expirées.

        Returns:
            Liste des certifications expirées
        """
        expired = []
        now = timezone.now()

        certifications = SellerCertification.objects.filter(
            revoked_at__isnull=True, expires_at__isnull=False, expires_at__lt=now
        )

        for certification in certifications:
            # Marquer comme expirée
            certification.revoked_at = now
            certification.revoked_by = None
            certification.revocation_reason = "Certification expirée"
            certification.save()

            # Journal d'audit
            from .models import CertificationAuditLog

            CertificationAuditLog.objects.create(
                user=certification.user,
                certification=certification,
                action=CertificationAuditLog.ActionType.CERTIFICATION_EXPIRED,
                actor=None,
                details={
                    "level": certification.level,
                    "expired_at": certification.expires_at.isoformat(),
                },
            )

            expired.append(certification)

        return expired


class RiskDetectionService:
    """Service de détection des comportements à risque."""

    def detect_risk_signals(self, user: User) -> List[RiskSignalModel]:
        """
        Détecte les signaux de risque pour un utilisateur.

        Args:
            user: L'utilisateur à analyser

        Returns:
            Liste des signaux de risque détectés
        """
        signals = []

        # 1. Vérifications répétées
        repeat_requests_signal = self._detect_repeated_verification_requests(user)
        if repeat_requests_signal:
            signals.append(repeat_requests_signal)

        # 2. Changements fréquents de profil
        frequent_changes_signal = self._detect_frequent_profile_changes(user)
        if frequent_changes_signal:
            signals.append(frequent_changes_signal)

        # 3. Comportements suspects dans les transactions
        suspicious_behavior_signal = self._detect_suspicious_behavior(user)
        if suspicious_behavior_signal:
            signals.append(suspicious_behavior_signal)

        # 4. Documents potentiellement dupliqués
        duplicate_docs_signal = self._detect_potential_duplicate_documents(user)
        if duplicate_docs_signal:
            signals.append(duplicate_docs_signal)

        return signals

    def _detect_repeated_verification_requests(
        self, user: User
    ) -> Optional[RiskSignalModel]:
        """Détecte les demandes de vérification répétées."""
        # Compte les demandes rejetées/révoquées récentes
        recent_rejected = VerificationRequest.objects.filter(
            user=user,
            status__in=["rejected", "cancelled"],
            created_at__gte=timezone.now() - timedelta(days=30),
        ).count()

        if recent_rejected >= 3:
            return RiskSignalModel(
                user=user,
                signal_type=RiskSignalModel.SignalType.REPEATED_VERIFICATION_REQUESTS,
                severity=RiskSignalModel.Severity.MEDIUM,
                description=f"{recent_rejected} demandes de vérification rejetées ou annulées dans les 30 derniers jours.",
                evidence={"rejected_count": recent_rejected},
                confidence_score=0.7,
                detected_by="system",
            )

        return None

    def _detect_frequent_profile_changes(self, user: User) -> Optional[RiskSignalModel]:
        """Détecte les changements fréquents de profil."""
        # Note: Implémentation simplifiée - nécessiterait un historique des changements
        # Pour l'instant, on vérifie les modifications récentes via updated_at
        recent_updates = VerificationRequest.objects.filter(
            user=user, updated_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        if recent_updates >= 5:
            return RiskSignalModel(
                user=user,
                signal_type=RiskSignalModel.SignalType.FREQUENT_PROFILE_CHANGES,
                severity=RiskSignalModel.Severity.LOW,
                description="Modifications fréquentes du profil ou des demandes de vérification.",
                evidence={"update_count": recent_updates},
                confidence_score=0.5,
                detected_by="system",
            )

        return None

    def _detect_suspicious_behavior(self, user: User) -> Optional[RiskSignalModel]:
        """Détecte les comportements suspects dans les transactions."""
        # Vérifier les transactions annulées récentes
        recent_cancelled = OrderItem.objects.filter(
            seller=user,
            order__status="cancelled",
            order__created_at__gte=timezone.now() - timedelta(days=30),
        ).count()

        total_recent = OrderItem.objects.filter(
            seller=user, order__created_at__gte=timezone.now() - timedelta(days=30)
        ).count()

        if total_recent > 0:
            cancellation_rate = (recent_cancelled / total_recent) * 100

            if cancellation_rate > 50:  # Plus de 50% d'annulations
                return RiskSignalModel(
                    user=user,
                    signal_type=RiskSignalModel.SignalType.SUSPICIOUS_BEHAVIOR,
                    severity=RiskSignalModel.Severity.HIGH,
                    description=f"Taux d'annulation élevé ({cancellation_rate:.1f}%) sur les transactions récentes.",
                    evidence={
                        "cancelled_count": recent_cancelled,
                        "total_count": total_recent,
                        "cancellation_rate": cancellation_rate,
                    },
                    confidence_score=0.8,
                    detected_by="system",
                )

        return None

    def _detect_potential_duplicate_documents(
        self, user: User
    ) -> Optional[RiskSignalModel]:
        """Détecte les documents potentiellement dupliqués."""
        from .models import VerificationDocument

        user_hashes = (
            VerificationDocument.objects.filter(
                request__user=user,
            )
            .exclude(content_sha256="")
            .values_list("content_sha256", flat=True)
        )
        duplicate_count = (
            VerificationDocument.objects.filter(
                content_sha256__in=user_hashes,
            )
            .exclude(request__user=user)
            .exclude(content_sha256="")
            .count()
        )
        if duplicate_count:
            return RiskSignalModel(
                user=user,
                signal_type=RiskSignalModel.SignalType.DUPLICATE_DOCUMENTS,
                severity=RiskSignalModel.Severity.MEDIUM,
                description="Un fichier identique a été transmis depuis un autre compte; une revue humaine est requise.",
                evidence={"matching_document_count": duplicate_count},
                confidence_score=0.9,
                detected_by="system",
            )
        return None


class DocumentValidationService:
    """Service de validation des documents."""

    @staticmethod
    def validate_document(document: "VerificationDocument") -> Tuple[bool, List[str]]:
        """
        Valide un document téléchargé.

        Args:
            document: Le document à valider

        Returns:
            Tuple (is_valid, error_messages)
        """
        errors = []

        # 1. Vérification de la taille
        max_size = 10 * 1024 * 1024  # 10 MB
        if document.file_size > max_size:
            errors.append(
                f"Taille maximale dépassée: {document.file_size} > {max_size}"
            )

        # 2. Vérification du type MIME
        allowed_mime_types = [
            "image/jpeg",
            "image/png",
            "image/heic",
            "image/heif",
            "application/pdf",
        ]

        if document.mime_type not in allowed_mime_types:
            errors.append(f"Type MIME non autorisé: {document.mime_type}")

        # 3. Vérification de la signature réelle du contenu
        try:
            with document.file.open("rb") as stored_file:
                signature = stored_file.read(16)
        except (OSError, ValueError):
            errors.append("Le fichier ne peut pas être lu depuis le stockage privé.")
            signature = b""

        actual_mime = ""
        if signature.startswith(b"\xff\xd8\xff"):
            actual_mime = "image/jpeg"
        elif signature.startswith(b"\x89PNG\r\n\x1a\n"):
            actual_mime = "image/png"
        elif signature.startswith(b"%PDF-"):
            actual_mime = "application/pdf"
        elif len(signature) >= 12 and signature[4:8] == b"ftyp":
            if signature[8:12] in {b"heic", b"heix", b"hevc", b"hevx"}:
                actual_mime = "image/heic"
            elif signature[8:12] == b"mif1":
                actual_mime = "image/heif"
        if actual_mime != document.mime_type:
            errors.append("Le contenu du fichier ne correspond pas au type déclaré.")

        # 4. Vérification de l'extension
        import os

        ext = os.path.splitext(document.original_filename)[1].lower()
        allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf", ".heic", ".heif"]

        if ext not in allowed_extensions:
            errors.append(f"Extension non autorisée: {ext}")

        return len(errors) == 0, errors


class CertificationCalculator:
    """Calcule automatiquement les certifications basées sur les données."""

    @staticmethod
    def calculate_automatic_certifications(user: User) -> List[str]:
        """
        Calcule les certifications automatiques pour un utilisateur.

        Returns:
            Liste des niveaux à attribuer automatiquement
        """
        certifications = []

        # Niveau 0: Toujours si compte actif
        if user.is_active:
            certifications.append(VerificationLevel.LEVEL_0_PROFILE_CREATED)

        # Niveau 1: Email vérifié
        if user.is_email_verified:
            certifications.append(VerificationLevel.LEVEL_1_EMAIL_VERIFIED)

        # Niveau 4: Historique fiable (calcul complexe)
        if CertificationCalculator._qualifies_for_reliable_history(user):
            certifications.append(VerificationLevel.LEVEL_4_RELIABLE_HISTORY)

        return certifications

    @staticmethod
    def _qualifies_for_reliable_history(user: User) -> bool:
        """Détermine si l'utilisateur qualifie pour le niveau 4."""
        service = VerificationService()
        criteria = service._get_criteria_by_level().get(
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY
        )
        return bool(criteria and service._check_level_eligibility(user, criteria))
