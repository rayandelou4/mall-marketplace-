import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import seller_verification.models
import seller_verification.storage


class Migration(migrations.Migration):

    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="VerificationRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "verification_type",
                    models.CharField(
                        choices=[
                            ("identity", "Document d'identité"),
                            ("business_registration", "Enregistrement commercial"),
                            ("business_location", "Localisation commerciale"),
                            ("business_activity", "Preuve d'activité commerciale"),
                            ("live_challenge", "Défi de vérification en direct"),
                        ],
                        max_length=30,
                        verbose_name="type de vérification",
                    ),
                ),
                (
                    "target_level",
                    models.CharField(
                        choices=[
                            ("level_0", "Profil créé"),
                            ("level_1", "E-mail vérifié"),
                            ("level_2", "Identité examinée"),
                            ("level_3", "Commerçant professionnel vérifié"),
                            ("level_4", "Historique commercial fiable"),
                        ],
                        max_length=20,
                        verbose_name="niveau ciblé",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Brouillon"),
                            ("pending", "En attente"),
                            (
                                "needs_more_info",
                                "Informations complémentaires demandées",
                            ),
                            ("under_review", "En cours d'examen"),
                            ("approved", "Approuvé"),
                            ("rejected", "Refusé"),
                            ("expired", "Expiré"),
                            ("cancelled", "Annulé"),
                        ],
                        default="draft",
                        max_length=20,
                        verbose_name="statut",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, verbose_name="description de la demande"
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date de soumission"
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date d'expiration"
                    ),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date d'examen"
                    ),
                ),
                (
                    "decision_notes",
                    models.TextField(blank=True, verbose_name="notes de décision"),
                ),
                (
                    "seller_message",
                    models.TextField(
                        blank=True, verbose_name="message communiqué au vendeur"
                    ),
                ),
                (
                    "rejection_reason",
                    models.TextField(blank=True, verbose_name="motif de refus"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_verification_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="examiné par",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="demandeur",
                    ),
                ),
            ],
            options={
                "db_table": "verification_requests",
                "ordering": ["-created_at"],
                "verbose_name": "demande de vérification",
                "verbose_name_plural": "demandes de vérification",
            },
        ),
        migrations.AddIndex(
            model_name="verificationrequest",
            index=models.Index(
                fields=["user", "status"], name="sv_request_user_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="verificationrequest",
            index=models.Index(
                fields=["status", "submitted_at"], name="sv_request_status_sub_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="verificationrequest",
            index=models.Index(fields=["expires_at"], name="sv_request_expires_idx"),
        ),
        migrations.AddConstraint(
            model_name="verificationrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    status__in=["draft", "pending", "under_review", "needs_more_info"]
                ),
                fields=("user", "verification_type"),
                name="unique_open_verification_request_per_type",
            ),
        ),
        migrations.CreateModel(
            name="SellerCertification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("level_0", "Profil créé"),
                            ("level_1", "E-mail vérifié"),
                            ("level_2", "Identité examinée"),
                            ("level_3", "Commerçant professionnel vérifié"),
                            ("level_4", "Historique commercial fiable"),
                        ],
                        max_length=20,
                        verbose_name="niveau de certification",
                    ),
                ),
                (
                    "granted_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="date d'attribution",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date d'expiration"
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="date de révocation"
                    ),
                ),
                (
                    "revocation_reason",
                    models.TextField(blank=True, verbose_name="motif de révocation"),
                ),
                ("notes", models.TextField(blank=True, verbose_name="notes internes")),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="granted_certifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="attribuée par",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revoked_certifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="révoquée par",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utilisateur",
                    ),
                ),
                (
                    "verification_request",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resulting_certification",
                        to="seller_verification.verificationrequest",
                        verbose_name="demande de vérification",
                    ),
                ),
            ],
            options={
                "db_table": "seller_certifications",
                "ordering": ["-granted_at"],
                "verbose_name": "certification de vendeur",
                "verbose_name_plural": "certifications de vendeurs",
            },
        ),
        migrations.AddIndex(
            model_name="sellercertification",
            index=models.Index(
                fields=["user", "level", "revoked_at"],
                name="sv_cert_user_level_rev_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sellercertification",
            index=models.Index(fields=["expires_at"], name="sv_cert_expires_idx"),
        ),
        migrations.AddIndex(
            model_name="sellercertification",
            index=models.Index(fields=["granted_at"], name="sv_cert_granted_idx"),
        ),
        migrations.AddConstraint(
            model_name="sellercertification",
            constraint=models.UniqueConstraint(
                condition=models.Q(revoked_at__isnull=True),
                fields=("user", "level"),
                name="unique_active_certification_per_level",
            ),
        ),
        migrations.CreateModel(
            name="VerificationCriteria",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("level_0", "Profil créé"),
                            ("level_1", "E-mail vérifié"),
                            ("level_2", "Identité examinée"),
                            ("level_3", "Commerçant professionnel vérifié"),
                            ("level_4", "Historique commercial fiable"),
                        ],
                        max_length=20,
                        unique=True,
                        verbose_name="niveau de certification",
                    ),
                ),
                (
                    "requires_profile",
                    models.BooleanField(
                        default=True, verbose_name="profil créé requis"
                    ),
                ),
                (
                    "requires_email_verification",
                    models.BooleanField(
                        default=False, verbose_name="email vérifié requis"
                    ),
                ),
                (
                    "requires_identity_verification",
                    models.BooleanField(
                        default=False, verbose_name="vérification d'identité requise"
                    ),
                ),
                (
                    "identity_verification_types",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="types de documents d'identité acceptés",
                    ),
                ),
                (
                    "requires_business_verification",
                    models.BooleanField(
                        default=False, verbose_name="vérification commerciale requise"
                    ),
                ),
                (
                    "business_verification_types",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="types de preuves commerciales acceptées",
                    ),
                ),
                (
                    "requires_transaction_count",
                    models.PositiveIntegerField(
                        default=0, verbose_name="nombre minimum de transactions"
                    ),
                ),
                (
                    "requires_account_age_days",
                    models.PositiveIntegerField(
                        default=0, verbose_name="ancienneté minimum du compte (jours)"
                    ),
                ),
                (
                    "requires_minimum_rating",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=3,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(5),
                        ],
                        verbose_name="note minimum",
                    ),
                ),
                (
                    "max_cancellation_rate",
                    models.DecimalField(
                        decimal_places=2,
                        default=100,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                        verbose_name="taux d'annulation maximum (%)",
                    ),
                ),
                (
                    "requires_no_active_disputes",
                    models.BooleanField(
                        default=False, verbose_name="aucun litige actif requis"
                    ),
                ),
                (
                    "is_automatic",
                    models.BooleanField(
                        default=False, verbose_name="attribution automatique"
                    ),
                ),
                (
                    "requires_admin_approval",
                    models.BooleanField(
                        default=True, verbose_name="approbation administrative requise"
                    ),
                ),
                (
                    "validity_period_days",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="période de validité (jours)",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="nom d'affichage"
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
                (
                    "benefits",
                    models.JSONField(
                        blank=True, default=list, verbose_name="avantages"
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="actif")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "verification_criteria",
                "verbose_name": "critères de vérification",
                "verbose_name_plural": "critères de vérification",
            },
        ),
        migrations.CreateModel(
            name="RiskSignal",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "signal_type",
                    models.CharField(
                        choices=[
                            ("multiple_accounts", "Multiples comptes"),
                            ("repeated_requests", "Demandes de vérification répétées"),
                            ("frequent_changes", "Changements fréquents de profil"),
                            (
                                "duplicate_documents",
                                "Documents identiques sur plusieurs comptes",
                            ),
                            ("suspicious_behavior", "Comportement suspect"),
                            ("abnormal_transactions", "Transactions anormales"),
                            ("high_risk_location", "Localisation à risque"),
                            ("other", "Autre"),
                        ],
                        max_length=30,
                        verbose_name="type de signal",
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("low", "Faible"),
                            ("medium", "Moyen"),
                            ("high", "Élevé"),
                            ("critical", "Critique"),
                        ],
                        default="medium",
                        max_length=10,
                        verbose_name="sévérité",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Actif"),
                            ("reviewed", "Examiné"),
                            ("resolved", "Résolu"),
                            ("false_positive", "Faux positif"),
                        ],
                        default="active",
                        max_length=20,
                        verbose_name="statut",
                    ),
                ),
                ("description", models.TextField(verbose_name="description")),
                (
                    "evidence",
                    models.JSONField(blank=True, default=dict, verbose_name="preuves"),
                ),
                (
                    "confidence_score",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.5,
                        max_digits=3,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                        verbose_name="score de confiance",
                    ),
                ),
                (
                    "detected_by",
                    models.CharField(
                        default="system", max_length=100, verbose_name="détecté par"
                    ),
                ),
                (
                    "review_notes",
                    models.TextField(blank=True, verbose_name="notes d'examen"),
                ),
                (
                    "action_taken",
                    models.TextField(blank=True, verbose_name="action entreprise"),
                ),
                ("detected_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_risk_signals",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="examiné par",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="risk_signals",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utilisateur",
                    ),
                ),
            ],
            options={
                "db_table": "risk_signals",
                "ordering": ["-detected_at"],
                "verbose_name": "signal de risque",
                "verbose_name_plural": "signaux de risque",
            },
        ),
        migrations.AddIndex(
            model_name="risksignal",
            index=models.Index(
                fields=["user", "status", "severity"],
                name="sv_risk_user_status_sev_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="risksignal",
            index=models.Index(
                fields=["signal_type", "status"], name="sv_risk_type_status_idx"
            ),
        ),
        migrations.CreateModel(
            name="VerificationDocument",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "document_type",
                    models.CharField(max_length=50, verbose_name="type de document"),
                ),
                (
                    "file",
                    models.FileField(
                        upload_to=seller_verification.models.verification_document_path,
                        storage=seller_verification.storage.private_verification_storage,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=[
                                    "jpg",
                                    "jpeg",
                                    "png",
                                    "pdf",
                                    "heic",
                                    "heif",
                                ]
                            )
                        ],
                        verbose_name="fichier",
                    ),
                ),
                (
                    "original_filename",
                    models.CharField(
                        max_length=255, verbose_name="nom de fichier original"
                    ),
                ),
                (
                    "file_size",
                    models.PositiveIntegerField(
                        verbose_name="taille du fichier (octets)"
                    ),
                ),
                (
                    "mime_type",
                    models.CharField(max_length=100, verbose_name="type MIME"),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
                (
                    "is_valid_format",
                    models.BooleanField(default=False, verbose_name="format valide"),
                ),
                (
                    "validation_errors",
                    models.JSONField(
                        blank=True, default=list, verbose_name="erreurs de validation"
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("retention_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "content_sha256",
                    models.CharField(blank=True, db_index=True, max_length=64),
                ),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="seller_verification.verificationrequest",
                        verbose_name="demande de vérification",
                    ),
                ),
            ],
            options={
                "db_table": "verification_documents",
                "ordering": ["uploaded_at"],
                "verbose_name": "document de vérification",
                "verbose_name_plural": "documents de vérification",
            },
        ),
        migrations.CreateModel(
            name="CertificationAuditLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("request_created", "Demande créée"),
                            ("request_submitted", "Demande soumise"),
                            ("request_reviewed", "Demande examinée"),
                            ("request_approved", "Demande approuvée"),
                            ("request_rejected", "Demande refusée"),
                            ("request_cancelled", "Demande annulée"),
                            ("request_expired", "Demande expirée"),
                            ("certification_granted", "Certification attribuée"),
                            ("certification_revoked", "Certification révoquée"),
                            ("certification_expired", "Certification expirée"),
                            ("document_uploaded", "Document téléchargé"),
                            ("document_validated", "Document validé"),
                            ("document_rejected", "Document rejeté"),
                            ("admin_action", "Action administrative"),
                            ("status_change", "Changement de statut"),
                        ],
                        max_length=30,
                        verbose_name="type d'action",
                    ),
                ),
                (
                    "details",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="détails de l'action"
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="adresse IP"
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(blank=True, verbose_name="agent utilisateur"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="performed_certification_actions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="acteur",
                    ),
                ),
                (
                    "certification",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="seller_verification.sellercertification",
                        verbose_name="certification concernée",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="seller_verification.verificationdocument",
                        verbose_name="document concerné",
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="seller_verification.verificationrequest",
                        verbose_name="demande concernée",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certification_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utilisateur concerné",
                    ),
                ),
            ],
            options={
                "db_table": "certification_audit_logs",
                "ordering": ["-created_at"],
                "verbose_name": "journal d'audit de certification",
                "verbose_name_plural": "journaux d'audit de certification",
            },
        ),
        migrations.AddIndex(
            model_name="certificationauditlog",
            index=models.Index(
                fields=["user", "created_at"], name="sv_audit_user_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="certificationauditlog",
            index=models.Index(
                fields=["action", "created_at"], name="sv_audit_action_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="certificationauditlog",
            index=models.Index(
                fields=["actor", "created_at"], name="sv_audit_actor_created_idx"
            ),
        ),
    ]
