"""
Vues de l'app `moderation`.
"""

from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from notifications.services import notify_moderation_event

from accounts.models import User

from .models import AccountModerationAction, Dispute, MessageReport, ModerationAction, ProductReport
from .serializers import (
    AccountModerationActionSerializer,
    DisputeCreateSerializer,
    DisputeSerializer,
    MessageReportCreateSerializer,
    MessageReportSerializer,
    ModeratedAccountSerializer,
    ProductReportCreateSerializer,
    ProductReportSerializer,
)


class IsModerationAdmin(permissions.BasePermission):
    """Require explicit Django model permissions for global moderation data."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        action = getattr(view, "action", None)
        if action in {"list", "retrieve"} and not request.user.is_staff:
            return True

        required_permission = getattr(view, "admin_permissions", {}).get(action)
        if required_permission:
            return request.user.is_staff and request.user.has_perm(required_permission)

        return action == "create"


@method_decorator(never_cache, name="dispatch")
class ProductReportViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsModerationAdmin]
    admin_permissions = {
        "list": "moderation.view_productreport",
        "retrieve": "moderation.view_productreport",
        "decide": "moderation.change_productreport",
    }

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return ProductReport.objects.select_related("product", "reporter", "seller").all()
        return ProductReport.objects.filter(reporter=user).select_related("product", "seller")

    def get_serializer_class(self):
        if self.action == "create":
            return ProductReportCreateSerializer
        return ProductReportSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(ProductReportSerializer(report).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        if not request.user.is_staff:
            raise PermissionDenied("Seuls les administrateurs peuvent décider d'un signalement.")

        report = self.get_object()
        decision = request.data.get("decision")
        reason = request.data.get("reason", "").strip()

        allowed = {"reject", "valid", "closed", "under_review"}
        if decision not in allowed:
            return Response({"detail": "Décision invalide."}, status=status.HTTP_400_BAD_REQUEST)

        allowed_status_map = {
            "reject": ProductReport.Status.REJECTED,
            "valid": ProductReport.Status.VALID,
            "closed": ProductReport.Status.CLOSED,
            "under_review": ProductReport.Status.UNDER_REVIEW,
        }
        report.status = allowed_status_map[decision]
        report.reviewed_by = request.user
        report.review_notes = reason
        report.save(update_fields=["status", "reviewed_by", "review_notes", "updated_at"])

        if decision == "valid" and report.is_high_risk:
            report.product.is_suspended = True
            report.product.suspension_reason = reason or "Suspension validée par un administrateur."
            report.product.suspended_by = request.user
            report.product.save(update_fields=["is_suspended", "suspension_reason", "suspended_by", "updated_at"])
            notify_moderation_event(
                report.product.seller,
                "listing_suspended",
                "Annonce suspendue",
                f"Votre annonce « {report.product.title} » a été suspendue après validation du signalement.",
                "/vendeur",
            )

        if decision == "reject":
            report.product.is_suspended = False
            report.product.suspension_reason = ""
            report.product.suspended_by = None
            report.product.save(update_fields=["is_suspended", "suspension_reason", "suspended_by", "updated_at"])

        notify_moderation_event(
            report.reporter,
            "report_decision",
            "Décision du modérateur",
            f"Le signalement sur « {report.product.title} » a été traité: {report.get_status_display()}.",
            "/notifications",
        )

        ModerationAction.objects.create(
            report=report,
            actor=request.user,
            action={
                "reject": ModerationAction.Action.REJECTED,
                "valid": ModerationAction.Action.RESOLVED,
                "closed": ModerationAction.Action.RESOLVED,
                "under_review": ModerationAction.Action.ASSIGNED,
            }[decision],
            details=reason,
        )
        return Response(ProductReportSerializer(report).data)


@method_decorator(never_cache, name="dispatch")
class DisputeViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsModerationAdmin]
    admin_permissions = {
        "list": "moderation.view_dispute",
        "retrieve": "moderation.view_dispute",
        "review": "moderation.change_dispute",
    }

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Dispute.objects.select_related("order", "seller", "raised_by", "reviewed_by").all()
        return Dispute.objects.filter(raised_by=user).select_related("order", "seller")

    def get_serializer_class(self):
        return DisputeCreateSerializer if self.action == "create" else DisputeSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        dispute = serializer.save()
        notify_moderation_event(
            dispute.seller,
            "dispute_opened",
            "Nouveau litige",
            f"Un litige a été ouvert sur votre commande #{dispute.order_id}.",
            "/mes-commandes",
        )
        return Response(DisputeSerializer(dispute, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        dispute = self.get_object()
        if not (request.user.is_staff or request.user == dispute.raised_by or request.user == dispute.seller):
            raise PermissionDenied("Vous n'avez pas le droit d'accéder à ce litige.")
        serializer = self.get_serializer(dispute, context={"request": request})
        return Response(serializer.data)

    @transaction.atomic
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        dispute = self.get_object()
        next_status = request.data.get("status")
        resolution = request.data.get("resolution", "")
        review_notes = request.data.get("review_notes", resolution)
        if not isinstance(resolution, str) or not isinstance(review_notes, str):
            return Response({"detail": "Les notes doivent être du texte."}, status=status.HTTP_400_BAD_REQUEST)
        resolution = resolution.strip()
        if next_status not in Dispute.Status.values:
            return Response({"detail": "Statut de litige invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if next_status in {Dispute.Status.RESOLVED, Dispute.Status.REJECTED} and not resolution:
            return Response(
                {"resolution": "Une décision motivée est requise pour clôturer ce litige."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispute.status = next_status
        dispute.resolution = resolution
        dispute.review_notes = review_notes.strip()
        dispute.handled_by = request.user
        dispute.reviewed_by = request.user
        dispute.resolved_at = (
            timezone.now()
            if next_status in {Dispute.Status.RESOLVED, Dispute.Status.REJECTED, Dispute.Status.CLOSED}
            else None
        )
        dispute.case_history = [
            *(dispute.case_history or []),
            {
                "actor": request.user.username,
                "status": next_status,
                "at": timezone.now().isoformat(),
                "notes": dispute.review_notes,
            },
        ]
        dispute.save(update_fields=[
            "status", "resolution", "review_notes", "handled_by", "reviewed_by",
            "resolved_at", "case_history", "updated_at",
        ])

        message = resolution or f"Le statut du litige est maintenant : {dispute.get_status_display()}."
        recipients = {dispute.raised_by_id: dispute.raised_by, dispute.seller_id: dispute.seller}
        for recipient in recipients.values():
            notify_moderation_event(
                recipient,
                "dispute_update",
                "Mise à jour de votre litige",
                message,
                "/mes-commandes",
            )

        return Response(DisputeSerializer(dispute, context={"request": request}).data)


@method_decorator(never_cache, name="dispatch")
class MessageReportViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsModerationAdmin]
    admin_permissions = {
        "list": "moderation.view_messagereport",
        "retrieve": "moderation.view_messagereport",
        "review": "moderation.change_messagereport",
    }

    def get_queryset(self):
        queryset = MessageReport.objects.select_related(
            "message", "conversation", "reporter", "reported_user", "reviewed_by"
        )
        if self.request.user.is_staff:
            return queryset.all()
        return queryset.filter(reporter=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return MessageReportCreateSerializer
        return MessageReportSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(
            MessageReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        report = self.get_object()
        next_status = request.data.get("status")
        notes = request.data.get("review_notes", "")
        if next_status not in MessageReport.Status.values:
            return Response({"detail": "Statut de signalement invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(notes, str):
            return Response({"review_notes": "La note doit être du texte."}, status=status.HTTP_400_BAD_REQUEST)
        report.status = next_status
        report.review_notes = notes.strip()
        report.reviewed_by = request.user
        report.save(update_fields=["status", "review_notes", "reviewed_by", "updated_at"])
        return Response(MessageReportSerializer(report, context={"request": request}).data)


@method_decorator(never_cache, name="dispatch")
class AccountModerationViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsModerationAdmin]
    admin_permissions = {"suspension": "accounts.change_user"}
    serializer_class = ModeratedAccountSerializer

    def get_queryset(self):
        return User.objects.filter(is_staff=False, is_superuser=False)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="suspension")
    def suspension(self, request, pk=None):
        account = self.get_object()
        suspended = request.data.get("suspended")
        reason = request.data.get("reason", "")
        if not isinstance(suspended, bool):
            return Response({"suspended": "Ce champ doit être un booléen."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            return Response({"reason": "Un motif de 1 à 2000 caractères est requis."}, status=status.HTTP_400_BAD_REQUEST)
        if suspended == account.is_suspended:
            return Response({"detail": "Le compte possède déjà cet état."}, status=status.HTTP_400_BAD_REQUEST)

        if suspended:
            account.suspension_previous_is_active = account.is_active
            account.is_active = False
            account.is_suspended = True
            account.suspension_reason = reason.strip()
            account.suspended_at = timezone.now()
            account.suspended_by = request.user
            action = AccountModerationAction.Action.SUSPENDED
        else:
            account.is_active = account.suspension_previous_is_active
            account.is_suspended = False
            account.suspension_reason = ""
            account.suspended_at = None
            account.suspended_by = None
            action = AccountModerationAction.Action.REINSTATED

        account.save(update_fields=[
            "is_active", "is_suspended", "suspension_reason", "suspended_at",
            "suspension_previous_is_active", "suspended_by",
        ])
        history = AccountModerationAction.objects.create(
            target_user=account,
            actor=request.user,
            action=action,
            reason=reason.strip(),
        )
        return Response({
            "account": ModeratedAccountSerializer(account).data,
            "action": AccountModerationActionSerializer(history).data,
        })
