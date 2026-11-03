"""
Interface d'administration Django pour le système de certification des vendeurs.

Fournit une interface sécurisée pour :
- Visualiser et gérer les demandes de vérification
- Examiner les documents (avec protection)
- Gérer les certifications
- Consulter les journaux d'audit
"""

import os
from datetime import timedelta
from django.contrib import admin, messages
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    SellerCertification,
    VerificationRequest,
    VerificationDocument,
    VerificationCriteria,
    RiskSignal,
    CertificationAuditLog,
    VerificationLevel,
    VerificationRequestStatus,
)
from .services import VerificationService
from notifications.services import notify


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    """Admin pour les demandes de vérification."""

    list_display = [
        "id_short",
        "user_info",
        "verification_type_display",
        "target_level_display",
        "status_display",
        "submitted_at",
        "reviewed_by_info",
        "review_button",
        "documents_button",
    ]

    list_filter = [
        "status",
        "verification_type",
        "target_level",
        "submitted_at",
        "reviewed_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "id",
    ]

    readonly_fields = [
        "id",
        "user",
        "status",
        "rejection_reason",
        "decision_notes",
        "reviewed_by",
        "submitted_at",
        "reviewed_at",
        "expires_at",
        "created_at",
        "updated_at",
        "documents_list",
        "audit_log",
    ]

    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "id",
                    "user",
                    "verification_type",
                    "target_level",
                    "description",
                )
            },
        ),
        (
            "Statut et décision",
            {
                "fields": (
                    "status",
                    "rejection_reason",
                    "decision_notes",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
        (
            "Dates",
            {"fields": ("submitted_at", "expires_at", "created_at", "updated_at")},
        ),
        (
            "Documents",
            {
                "fields": ("documents_list",),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": ("audit_log",),
                "classes": ("collapse",),
            },
        ),
    )

    actions = []

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        if not request.user.has_perm("seller_verification.view_verificationdocument"):
            return tuple(field for field in fields if field != "documents_button")
        return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.has_perm("seller_verification.view_verificationdocument"):
            return fieldsets
        return tuple(
            (
                name,
                {
                    **options,
                    "fields": tuple(
                        field
                        for field in options["fields"]
                        if field != "documents_list"
                    ),
                },
            )
            for name, options in fieldsets
            if any(field != "documents_list" for field in options["fields"])
        )

    def id_short(self, obj):
        """Affiche un ID court."""
        return str(obj.id)[:8] + "..."

    id_short.short_description = "ID"

    def user_info(self, obj):
        """Affiche les informations utilisateur."""
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.user.username,
            obj.user.email,
        )

    user_info.short_description = "Utilisateur"

    def verification_type_display(self, obj):
        """Affiche le type de vérification."""
        return obj.get_verification_type_display()

    verification_type_display.short_description = "Type"

    def target_level_display(self, obj):
        """Affiche le niveau ciblé."""
        return obj.get_target_level_display()

    target_level_display.short_description = "Niveau"

    def status_display(self, obj):
        """Affiche le statut avec couleur."""
        colors = {
            VerificationRequestStatus.DRAFT: "gray",
            VerificationRequestStatus.PENDING: "orange",
            VerificationRequestStatus.UNDER_REVIEW: "blue",
            VerificationRequestStatus.NEEDS_MORE_INFORMATION: "yellow",
            VerificationRequestStatus.APPROVED: "green",
            VerificationRequestStatus.REJECTED: "red",
            VerificationRequestStatus.EXPIRED: "gray",
            VerificationRequestStatus.CANCELLED: "gray",
        }

        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "Statut"

    def reviewed_by_info(self, obj):
        """Affiche l'information sur l'examinateur."""
        if obj.reviewed_by:
            url = reverse("admin:accounts_user_change", args=[obj.reviewed_by.id])
            return format_html(
                '<a href="{}">{}</a><br><small>{}</small>',
                url,
                obj.reviewed_by.username,
                obj.reviewed_at.strftime("%d/%m/%Y %H:%M") if obj.reviewed_at else "",
            )
        return "-"

    reviewed_by_info.short_description = "Examiné par"

    def review_button(self, obj):
        if obj.status in [
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.UNDER_REVIEW,
        ]:
            url = reverse(
                "admin:seller_verification_verificationrequest_review", args=[obj.id]
            )
            return format_html(
                '<a href="{}" class="button">Examiner</a>',
                url,
            )
        return "-"

    review_button.short_description = "Revue"

    def documents_button(self, obj):
        if obj.documents.exists():
            url = reverse(
                "admin:seller_verification_verificationrequest_documents", args=[obj.id]
            )
            return format_html(
                '<a href="{}" class="button">Documents ({})</a>',
                url,
                obj.documents.count(),
            )
        return "-"

    documents_button.short_description = "Pièces"

    def documents_list(self, obj):
        """Affiche la liste des documents."""
        documents = obj.documents.all()

        if not documents:
            return "Aucun document"

        html = '<ul style="margin-left: 0; padding-left: 20px;">'
        for doc in documents:
            html += format_html(
                '<li><strong>{}</strong> ({}, {:.2f} MB) - <a href="{}" target="_blank">Télécharger</a></li>',
                doc.document_type,
                doc.original_filename,
                doc.file_size / (1024 * 1024),
                reverse(
                    "admin:seller_verification_verificationrequest_document_download",
                    args=[obj.id, doc.id],
                ),
            )
        html += "</ul>"

        return mark_safe(html)

    documents_list.short_description = "Documents"

    def audit_log(self, obj):
        """Affiche le journal d'audit."""
        logs = CertificationAuditLog.objects.filter(request=obj).order_by("-created_at")

        if not logs:
            return "Aucun événement d'audit"

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background-color: #f8f9fa;"><th>Date</th><th>Action</th><th>Acteur</th><th>Détails</th></tr>'

        for log in logs:
            html += format_html(
                '<tr style="border-bottom: 1px solid #dee2e6;">'
                '<td style="padding: 8px;">{}</td>'
                '<td style="padding: 8px;">{}</td>'
                '<td style="padding: 8px;">{}</td>'
                '<td style="padding: 8px;">{}</td>'
                "</tr>",
                log.created_at.strftime("%d/%m/%Y %H:%M"),
                log.get_action_display(),
                log.actor.username if log.actor else "Système",
                (
                    str(log.details)[:100] + "..."
                    if len(str(log.details)) > 100
                    else str(log.details)
                ),
            )

        html += "</table>"

        return mark_safe(html)

    audit_log.short_description = "Journal d'audit"

    def approve_selected(self, request, queryset):
        """Approuve les demandes sélectionnées."""
        if not request.user.has_perm("seller_verification.change_verificationrequest"):
            raise PermissionDenied

        service = VerificationService()
        approved = 0
        errors = []

        for request_obj in queryset:
            if request_obj.status in [
                VerificationRequestStatus.PENDING,
                VerificationRequestStatus.UNDER_REVIEW,
            ]:
                try:
                    service.grant_certification(
                        user=request_obj.user,
                        level=request_obj.target_level,
                        granted_by=request.user,
                        verification_request=request_obj,
                        notes="Approuvé via l'interface admin",
                    )

                    request_obj.status = VerificationRequestStatus.APPROVED
                    request_obj.reviewed_by = request.user
                    request_obj.reviewed_at = timezone.now()
                    request_obj.save()

                    approved += 1

                except Exception as e:
                    errors.append(f"{request_obj.id}: {str(e)}")

        if approved:
            self.message_user(
                request, f"{approved} demande(s) approuvée(s).", messages.SUCCESS
            )
        if errors:
            self.message_user(request, f"Erreurs: {', '.join(errors)}", messages.ERROR)

    approve_selected.short_description = "Approuver les demandes sélectionnées"

    def reject_selected(self, request, queryset):
        """Rejette les demandes sélectionnées."""
        if not request.user.has_perm("seller_verification.change_verificationrequest"):
            raise PermissionDenied

        rejected = 0

        for request_obj in queryset:
            if request_obj.status in [
                VerificationRequestStatus.PENDING,
                VerificationRequestStatus.UNDER_REVIEW,
            ]:
                request_obj.status = VerificationRequestStatus.REJECTED
                request_obj.reviewed_by = request.user
                request_obj.reviewed_at = timezone.now()
                request_obj.rejection_reason = "Rejeté via l'interface admin"
                request_obj.save()

                # Log d'audit
                CertificationAuditLog.objects.create(
                    user=request_obj.user,
                    request=request_obj,
                    action=CertificationAuditLog.ActionType.REQUEST_REJECTED,
                    actor=request.user,
                    details={"action": "bulk_reject"},
                )

                rejected += 1

        if rejected:
            self.message_user(
                request, f"{rejected} demande(s) rejetée(s).", messages.SUCCESS
            )

    reject_selected.short_description = "Rejeter les demandes sélectionnées"

    def request_more_info_selected(self, request, queryset):
        """Demande plus d'informations pour les demandes sélectionnées."""
        if not request.user.has_perm("seller_verification.change_verificationrequest"):
            raise PermissionDenied

        updated = 0

        for request_obj in queryset:
            if request_obj.status in [
                VerificationRequestStatus.PENDING,
                VerificationRequestStatus.UNDER_REVIEW,
            ]:
                request_obj.status = VerificationRequestStatus.NEEDS_MORE_INFORMATION
                request_obj.reviewed_by = request.user
                request_obj.reviewed_at = timezone.now()
                request_obj.decision_notes = (
                    "Informations supplémentaires demandées via l'interface admin"
                )
                request_obj.save()

                updated += 1

        if updated:
            self.message_user(
                request, f"{updated} demande(s) mise(s) à jour.", messages.SUCCESS
            )

    request_more_info_selected.short_description = "Demander plus d'informations"

    def get_urls(self):
        """Ajoute des URLs personnalisées."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:request_id>/review/",
                self.admin_site.admin_view(self.review_view),
                name="seller_verification_verificationrequest_review",
            ),
            path(
                "<uuid:request_id>/documents/",
                self.admin_site.admin_view(self.documents_view),
                name="seller_verification_verificationrequest_documents",
            ),
            path(
                "<uuid:request_id>/documents/<uuid:document_id>/download/",
                self.admin_site.admin_view(self.document_download_view),
                name="seller_verification_verificationrequest_document_download",
            ),
        ]
        return custom_urls + urls

    def review_view(self, request, request_id):
        """Vue pour examiner une demande."""
        if not request.user.has_perm("seller_verification.change_verificationrequest"):
            raise PermissionDenied

        verification_request = get_object_or_404(VerificationRequest, id=request_id)

        if verification_request.user_id == request.user.id:
            raise PermissionDenied("Vous ne pouvez pas examiner votre propre demande.")

        if verification_request.status not in [
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.UNDER_REVIEW,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        ]:
            self.message_user(
                request, "Cette demande n'est plus ouverte à l'examen.", messages.ERROR
            )
            return redirect(
                "admin:seller_verification_verificationrequest_change",
                verification_request.id,
            )

        if request.method == "POST":
            decision = request.POST.get("decision")
            notes = request.POST.get("notes", "")
            rejection_reason = request.POST.get("rejection_reason", "")
            seller_message = request.POST.get("seller_message", "").strip()

            if decision == "reject" and not rejection_reason.strip():
                self.message_user(
                    request,
                    "Un motif de refus destiné au vendeur est requis.",
                    messages.ERROR,
                )
                return redirect(
                    "admin:seller_verification_verificationrequest_review",
                    verification_request.id,
                )

            service = VerificationService()

            try:
                if decision == "approve":
                    if (
                        not verification_request.documents.filter(
                            is_valid_format=True
                        ).exists()
                        or verification_request.documents.filter(
                            is_valid_format=False
                        ).exists()
                    ):
                        raise ValueError(
                            "La demande doit contenir au moins une pièce valide et aucune pièce invalide."
                        )
                    certification = service.grant_certification(
                        user=verification_request.user,
                        level=verification_request.target_level,
                        granted_by=request.user,
                        verification_request=verification_request,
                        notes=notes,
                    )

                    verification_request.status = VerificationRequestStatus.APPROVED
                    verification_request.reviewed_by = request.user
                    verification_request.reviewed_at = timezone.now()
                    verification_request.decision_notes = notes
                    verification_request.save()
                    verification_request.documents.update(
                        retention_expires_at=timezone.now() + timedelta(days=90)
                    )

                    CertificationAuditLog.objects.create(
                        user=verification_request.user,
                        request=verification_request,
                        certification=certification,
                        action=CertificationAuditLog.ActionType.REQUEST_APPROVED,
                        actor=request.user,
                        details={"level": verification_request.target_level},
                    )
                    notify(
                        verification_request.user,
                        "verification_update",
                        "Demande approuvée",
                        "Votre demande a été approuvée. La vérification est interne et ne garantit pas l’absence de fraude.",
                        "/vendeur?section=verification",
                    )

                    self.message_user(
                        request, "Demande approuvée avec succès.", messages.SUCCESS
                    )
                    return redirect(
                        "admin:seller_verification_verificationrequest_change",
                        verification_request.id,
                    )

                elif decision == "reject":
                    verification_request.status = VerificationRequestStatus.REJECTED
                    verification_request.reviewed_by = request.user
                    verification_request.reviewed_at = timezone.now()
                    verification_request.decision_notes = notes
                    verification_request.rejection_reason = rejection_reason
                    verification_request.save()
                    verification_request.documents.update(
                        retention_expires_at=timezone.now() + timedelta(days=90)
                    )

                    # Log d'audit
                    CertificationAuditLog.objects.create(
                        user=verification_request.user,
                        request=verification_request,
                        action=CertificationAuditLog.ActionType.REQUEST_REJECTED,
                        actor=request.user,
                        details={"notes": notes, "rejection_reason": rejection_reason},
                    )
                    notify(
                        verification_request.user,
                        "verification_update",
                        "Demande refusée",
                        f"Votre demande a été refusée. Motif : {rejection_reason}",
                        "/vendeur?section=verification",
                    )

                    self.message_user(request, "Demande rejetée.", messages.SUCCESS)
                    return redirect(
                        "admin:seller_verification_verificationrequest_change",
                        verification_request.id,
                    )

                elif decision == "request_more_info":
                    if not seller_message:
                        raise ValueError(
                            "Indiquez les informations à fournir au vendeur."
                        )
                    verification_request.status = (
                        VerificationRequestStatus.NEEDS_MORE_INFORMATION
                    )
                    verification_request.reviewed_by = request.user
                    verification_request.reviewed_at = timezone.now()
                    verification_request.decision_notes = notes
                    verification_request.seller_message = seller_message
                    verification_request.save()
                    CertificationAuditLog.objects.create(
                        user=verification_request.user,
                        request=verification_request,
                        action=CertificationAuditLog.ActionType.STATUS_CHANGE,
                        actor=request.user,
                        details={
                            "new_status": VerificationRequestStatus.NEEDS_MORE_INFORMATION,
                            "message_sent": True,
                        },
                    )
                    notify(
                        verification_request.user,
                        "verification_update",
                        "Informations requises",
                        seller_message,
                        "/vendeur?section=verification",
                    )

                    self.message_user(
                        request,
                        "Informations supplémentaires demandées.",
                        messages.SUCCESS,
                    )
                    return redirect(
                        "admin:seller_verification_verificationrequest_change",
                        verification_request.id,
                    )

            except Exception as e:
                self.message_user(request, f"Erreur: {str(e)}", messages.ERROR)

        # Context pour le template
        context = {
            **self.admin_site.each_context(request),
            "verification_request": verification_request,
            "title": f"Examiner la demande {verification_request.id}",
            "opts": self.model._meta,
        }

        return self.admin_site.admin_view(self.review_template)(request, context)

    def review_template(self, request, context):
        """Template pour l'examen d'une demande."""
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "admin/seller_verification/verificationrequest/review.html",
            context,
        )

    def documents_view(self, request, request_id):
        """Vue pour afficher les documents d'une demande."""
        if not request.user.has_perm("seller_verification.view_verificationdocument"):
            raise PermissionDenied

        verification_request = get_object_or_404(VerificationRequest, id=request_id)

        context = {
            **self.admin_site.each_context(request),
            "verification_request": verification_request,
            "documents": verification_request.documents.all(),
            "title": f"Documents - Demande {verification_request.id}",
            "opts": self.model._meta,
        }

        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "admin/seller_verification/verificationrequest/documents.html",
            context,
        )

    def document_download_view(self, request, request_id, document_id):
        """Vue pour télécharger un document."""
        if not request.user.has_perm("seller_verification.view_verificationdocument"):
            raise PermissionDenied

        document = get_object_or_404(
            VerificationDocument, id=document_id, request_id=request_id
        )

        # Vérifier que le fichier existe
        if not document.file or not document.file.storage.exists(document.file.name):
            raise Http404("Document non trouvé.")

        # Log d'audit de l'accès
        CertificationAuditLog.objects.create(
            user=document.request.user,
            request=document.request,
            document=document,
            action=CertificationAuditLog.ActionType.ADMIN_ACTION,
            actor=request.user,
            details={
                "action": "document_download_admin",
            },
        )

        response = FileResponse(
            document.file.open("rb"), content_type=document.mime_type
        )
        response["Content-Disposition"] = 'attachment; filename="verification-document"'
        return response


@admin.register(SellerCertification)
class SellerCertificationAdmin(admin.ModelAdmin):
    """Admin pour les certifications des vendeurs."""

    list_display = [
        "id_short",
        "user_info",
        "level_display",
        "granted_at",
        "expires_at_display",
        "revoked_display",
        "is_active_display",
        "revoke_button",
    ]

    list_filter = [
        "level",
        "revoked_at",
        "granted_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "id",
    ]

    readonly_fields = [
        "id",
        "user",
        "verification_request",
        "granted_at",
        "expires_at",
        "revoked_at",
        "granted_by",
        "revoked_by",
        "revocation_reason",
        "notes",
    ]

    fieldsets = (
        (
            "Informations générales",
            {"fields": ("id", "user", "level", "verification_request")},
        ),
        ("Dates", {"fields": ("granted_at", "expires_at", "revoked_at")}),
        ("Personnel", {"fields": ("granted_by", "revoked_by")}),
        ("Notes", {"fields": ("revocation_reason", "notes")}),
    )

    actions = []

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "<uuid:certification_id>/revoke/",
                self.admin_site.admin_view(self.revoke_view),
                name="seller_verification_sellercertification_revoke",
            ),
        ] + urls

    def revoke_view(self, request, certification_id):
        if not request.user.has_perm("seller_verification.change_sellercertification"):
            raise PermissionDenied
        certification = get_object_or_404(SellerCertification, id=certification_id)
        if request.method == "POST":
            reason = request.POST.get("reason", "").strip()
            if request.POST.get("confirmed") != "on" or not reason:
                self.message_user(
                    request, "Confirmez l'action et indiquez un motif.", messages.ERROR
                )
            else:
                VerificationService().revoke_certification(
                    certification, request.user, reason
                )
                notify(
                    certification.user,
                    "verification_update",
                    "Certification révoquée",
                    "Une certification de votre compte a été révoquée. Consultez votre espace vendeur pour plus d'informations.",
                    "/vendeur?section=verification",
                )
                return redirect(
                    "admin:seller_verification_sellercertification_changelist"
                )
        from django.template.response import TemplateResponse

        return TemplateResponse(
            request,
            "admin/seller_verification/sellercertification/revoke.html",
            {
                **self.admin_site.each_context(request),
                "certification": certification,
                "title": "Révoquer la certification",
                "opts": self.model._meta,
            },
        )

    def id_short(self, obj):
        """Affiche un ID court."""
        return str(obj.id)[:8] + "..."

    id_short.short_description = "ID"

    def user_info(self, obj):
        """Affiche les informations utilisateur."""
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br><small>{}</small>',
            url,
            obj.user.username,
            obj.user.email,
        )

    user_info.short_description = "Utilisateur"

    def level_display(self, obj):
        """Affiche le niveau de certification."""
        return obj.get_level_display()

    level_display.short_description = "Niveau"

    def expires_at_display(self, obj):
        """Affiche la date d'expiration."""
        if obj.expires_at:
            days_left = (obj.expires_at - timezone.now()).days

            if days_left < 0:
                return format_html(
                    '<span style="color: red; font-weight: bold;">Expiré</span><br><small>{}</small>',
                    obj.expires_at.strftime("%d/%m/%Y"),
                )
            elif days_left < 30:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">{} jours</span><br><small>{}</small>',
                    days_left,
                    obj.expires_at.strftime("%d/%m/%Y"),
                )
            else:
                return format_html(
                    "{}<br><small>{}</small>",
                    f"{days_left} jours",
                    obj.expires_at.strftime("%d/%m/%Y"),
                )
        return "Pas d'expiration"

    expires_at_display.short_description = "Expiration"

    def revoked_display(self, obj):
        """Affiche l'information de révocation."""
        if obj.revoked_at:
            return format_html(
                '<span style="color: red; font-weight: bold;">Oui</span><br><small>{}</small>',
                obj.revoked_at.strftime("%d/%m/%Y"),
            )
        return format_html('<span style="color: green;">Non</span>')

    revoked_display.short_description = "Révoquée"

    def is_active_display(self, obj):
        """Affiche si la certification est active."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">● Actif</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">● Inactif</span>'
            )

    is_active_display.short_description = "Statut"

    def revoke_button(self, obj):
        if not obj.is_active:
            return "-"
        url = reverse(
            "admin:seller_verification_sellercertification_revoke", args=[obj.id]
        )
        return format_html('<a href="{}" class="button">Révoquer</a>', url)

    revoke_button.short_description = "Action"

    def revoke_selected(self, request, queryset):
        """Révoque les certifications sélectionnées."""
        if not request.user.has_perm("seller_verification.change_sellercertification"):
            raise PermissionDenied

        service = VerificationService()
        revoked = 0
        errors = []

        for certification in queryset:
            if certification.is_active:
                try:
                    service.revoke_certification(
                        certification, request.user, "Révoqué via l'interface admin"
                    )
                    revoked += 1
                except Exception as e:
                    errors.append(f"{certification.id}: {str(e)}")

        if revoked:
            self.message_user(
                request, f"{revoked} certification(s) révoquée(s).", messages.SUCCESS
            )
        if errors:
            self.message_user(request, f"Erreurs: {', '.join(errors)}", messages.ERROR)

    revoke_selected.short_description = "Révoquer les certifications sélectionnées"
