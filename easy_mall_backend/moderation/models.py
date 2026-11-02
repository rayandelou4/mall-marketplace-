"""
Modèle de l'app `moderation`.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ProductReport(models.Model):
    class Reason(models.TextChoices):
        COUNTERFEIT_PRODUCT = "counterfeit_product", _("Produit potentiellement contrefait")
        MISLEADING_DESCRIPTION = "misleading_description", _("Description trompeuse")
        MISLEADING_PHOTOS = "misleading_photos", _("Photos trompeuses")
        PROHIBITED_PRODUCT = "prohibited_product", _("Produit interdit")
        SCAM_SUSPECTED = "scam_suspected", _("Suspicion d'arnaque")
        MISLEADING_PRICING = "misleading_pricing", _("Prix ou caractéristiques trompeurs")
        DUPLICATE_OR_SPAM = "duplicate_or_spam", _("Annonce dupliquée ou spam")
        OTHER = "other", _("Autre motif")

    class Status(models.TextChoices):
        NEW = "new", _("Nouveau")
        UNDER_REVIEW = "under_review", _("En cours d'examen")
        VALID = "valid", _("Fondé")
        REJECTED = "rejected", _("Rejeté")
        CLOSED = "closed", _("Clôturé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reports"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reports_received",
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    is_high_risk = models.BooleanField(default=False)
    evidence = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_reports_reviewed",
    )
    review_notes = models.TextField(blank=True)

    class Meta:
        db_table = "product_reports"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "reporter"],
                condition=models.Q(status__in=["new", "under_review", "valid"]),
                name="unique_active_product_report_per_user",
            )
        ]

    def __str__(self):
        return f"Signalement {self.id} — {self.get_reason_display()}"

    @property
    def is_active(self):
        return self.status in {self.Status.NEW, self.Status.UNDER_REVIEW, self.Status.VALID}

    @property
    def is_serious_risk(self):
        return self.reason in {
            self.Reason.COUNTERFEIT_PRODUCT,
            self.Reason.PROHIBITED_PRODUCT,
            self.Reason.SCAM_SUSPECTED,
            self.Reason.MISLEADING_PRICING,
        }


class ModerationAction(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", _("Créé")
        ASSIGNED = "assigned", _("Assigné")
        SUSPENDED = "suspended", _("Suspendue")
        REINSTATED = "reinstated", _("Rétablie")
        REMOVED = "removed", _("Retirée")
        REJECTED = "rejected", _("Rejeté")
        NEEDS_MORE_INFO = "needs_more_info", _("Informations complémentaires demandées")
        RESOLVED = "resolved", _("Résolu")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ProductReport, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="moderation_actions")
    action = models.CharField(max_length=25, choices=Action.choices)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "moderation_actions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.report_id}"


class Dispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Ouvert")
        WAITING_SELLER = "waiting_seller", _("En attente du vendeur")
        WAITING_BUYER = "waiting_buyer", _("En attente de l'acheteur")
        UNDER_REVIEW = "under_review", _("En cours d'examen")
        RESOLVED = "resolved", _("Résolu")
        REJECTED = "rejected", _("Rejeté")
        CLOSED = "closed", _("Clôturé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="disputes")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="disputes_as_seller",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="disputes_raised"
    )
    reason = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_handled",
    )
    evidence = models.JSONField(default=list, blank=True)
    private_evidence = models.JSONField(default=list, blank=True)
    case_history = models.JSONField(default=list, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_reviewed",
    )
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "disputes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Litige {self.id} — {self.get_status_display()}"
