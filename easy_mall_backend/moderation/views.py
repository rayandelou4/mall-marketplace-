"""
Vues de l'app `moderation`.
"""

from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from notifications.services import notify_moderation_event

from .models import Dispute, ModerationAction, ProductReport
from .serializers import (
    DisputeCreateSerializer,
    DisputeSerializer,
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
    }

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Dispute.objects.select_related("order", "seller", "raised_by").all()
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
