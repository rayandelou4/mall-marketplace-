"""
Serializers de l'app `moderation`.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from catalog.models import Product
from orders.models import Order

from .models import Dispute, ModerationAction, ProductReport


class ProductReportSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    action_history = serializers.SerializerMethodField()

    class Meta:
        model = ProductReport
        fields = [
            "id", "product_id", "product", "seller", "seller_username",
            "reporter", "reporter_username", "reason", "reason_display",
            "description", "status", "status_display", "is_high_risk",
            "evidence", "review_notes", "action_history", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_action_history(self, obj):
        return list(obj.history.values("id", "action", "details", "created_at", "actor__username"))


class ProductReportCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=ProductReport.Reason.choices)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def validate_product_id(self, value):
        request = self.context["request"]
        try:
            product = Product.objects.select_related("seller").get(pk=value)
        except Product.DoesNotExist as exc:
            raise serializers.ValidationError("Annonce introuvable.") from exc

        if product.seller_id == request.user.id:
            raise serializers.ValidationError("Vous ne pouvez pas signaler votre propre annonce.")

        if ProductReport.objects.filter(
            product=product,
            reporter=request.user,
            status__in=[ProductReport.Status.NEW, ProductReport.Status.UNDER_REVIEW, ProductReport.Status.VALID],
        ).exists():
            raise serializers.ValidationError("Vous avez déjà signalé cette annonce pour un dossier actif.")

        self.product = product
        return value

    @transaction.atomic
    def save(self):
        request = self.context["request"]
        product = self.product
        reason = self.validated_data["reason"]
        description = self.validated_data.get("description", "")
        serious_reasons = {
            ProductReport.Reason.COUNTERFEIT_PRODUCT,
            ProductReport.Reason.PROHIBITED_PRODUCT,
            ProductReport.Reason.SCAM_SUSPECTED,
            ProductReport.Reason.MISLEADING_PRICING,
        }

        report = ProductReport.objects.create(
            product=product,
            reporter=request.user,
            seller=product.seller,
            reason=reason,
            description=description,
            is_high_risk=reason in serious_reasons,
            evidence=[{"author": request.user.username, "message": description, "source": "report"}],
        )

        if report.is_high_risk:
            product.is_suspended = True
            product.suspension_reason = "Suspension temporaire déclenchée par un signalement à risque élevé."
            product.status_before_suspension = product.status
            product.suspended_at = timezone.now()
            product.save(update_fields=["is_suspended", "suspension_reason", "status_before_suspension", "suspended_at"])

        ModerationAction.objects.create(
            report=report,
            actor=request.user,
            action=ModerationAction.Action.CREATED,
            details="Signalement reçu avant examen administratif.",
        )
        return report


class DisputeSerializer(serializers.ModelSerializer):
    order_status = serializers.CharField(source="order.status", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    raised_by_username = serializers.CharField(source="raised_by.username", read_only=True)
    can_view_private_evidence = serializers.SerializerMethodField()
    evidence_view = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            "id", "order", "order_status", "seller", "seller_username",
            "raised_by", "raised_by_username", "reason", "description", "status",
            "resolution", "evidence", "private_evidence", "case_history", "review_notes",
            "can_view_private_evidence", "evidence_view", "created_at", "updated_at", "resolved_at",
        ]
        read_only_fields = fields

    def get_can_view_private_evidence(self, obj):
        user = self.context.get("request").user
        return bool(user.is_staff or user == obj.raised_by or user == obj.seller)

    def get_evidence_view(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        if not user or not (user.is_staff or user == obj.raised_by or user == obj.seller):
            return []
        return obj.private_evidence or obj.evidence


class DisputeCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=40)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def validate_order_id(self, value):
        request = self.context["request"]
        try:
            order = Order.objects.select_related("buyer").prefetch_related("items__seller").get(pk=value, buyer=request.user)
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError("Commande introuvable pour cet utilisateur.") from exc

        if order.items.count() == 0:
            raise serializers.ValidationError("Cette commande ne contient aucun article.")
        if order.status in {Order.Status.CANCELLED, Order.Status.REFUNDED}:
            raise serializers.ValidationError("Un litige ne peut pas être ouvert sur une commande annulée ou remboursée.")

        self.order = order
        return value

    @transaction.atomic
    def save(self):
        request = self.context["request"]
        order = self.order
        seller = order.items.select_related("seller").order_by("seller_id").first().seller

        dispute = Dispute.objects.create(
            order=order,
            seller=seller,
            raised_by=request.user,
            reason=self.validated_data["reason"],
            description=self.validated_data.get("description", ""),
            evidence=[{"author": request.user.username, "message": self.validated_data.get("description", ""), "source": "dispute"}],
            private_evidence=[{"author": request.user.username, "message": self.validated_data.get("description", ""), "source": "private_dispute"}],
            case_history=[{"actor": request.user.username, "status": "open", "at": timezone.now().isoformat()}],
        )
        order.status = Order.Status.DISPUTED
        order.save(update_fields=["status"])
        return dispute
