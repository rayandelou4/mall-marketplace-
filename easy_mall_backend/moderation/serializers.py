"""
Serializers de l'app `moderation`.
"""

from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from catalog.models import Product
from accounts.models import User
from messaging.models import Message
from orders.models import Order

from .models import AccountModerationAction, Dispute, DisputeMessage, MessageReport, ModerationAction, ProductReport


class ProductReportSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    seller_is_suspended = serializers.BooleanField(source="seller.is_suspended", read_only=True)
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    action_history = serializers.SerializerMethodField()

    class Meta:
        model = ProductReport
        fields = [
            "id", "product_id", "product", "seller", "seller_username", "seller_is_suspended",
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

        ModerationAction.objects.create(
            report=report,
            actor=request.user,
            action=ModerationAction.Action.CREATED,
            details="Signalement reçu avant examen administratif.",
        )
        return report


class DisputeSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    seller_is_suspended = serializers.BooleanField(source="seller.is_suspended", read_only=True)
    raised_by_username = serializers.CharField(source="raised_by.username", read_only=True)
    raised_by_is_suspended = serializers.BooleanField(source="raised_by.is_suspended", read_only=True)
    can_view_private_evidence = serializers.SerializerMethodField()
    evidence_view = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()
    appeal_allowed = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            "id", "order", "order_status", "seller", "seller_username", "seller_is_suspended",
            "raised_by", "raised_by_username", "raised_by_is_suspended", "reason", "reason_display", "description", "status",
            "resolution", "evidence", "private_evidence", "case_history", "review_notes",
            "appeal_deadline", "appealed_at", "appeal_allowed", "refund_status",
            "refund_amount", "refund_reference", "messages",
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

    def get_messages(self, obj):
        return DisputeMessageSerializer(
            obj.messages.select_related("author").all(), many=True
        ).data

    def get_appeal_allowed(self, obj):
        request = self.context.get("request")
        if not request or request.user not in (obj.raised_by, obj.seller):
            return False
        return bool(
            obj.status in {Dispute.Status.RESOLVED, Dispute.Status.REJECTED, Dispute.Status.CLOSED}
            and obj.appeal_deadline
            and obj.appeal_deadline > timezone.now()
        )


class DisputeMessageSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True, allow_null=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = DisputeMessage
        fields = ["id", "author", "author_username", "kind", "kind_display", "body", "evidence", "created_at"]
        read_only_fields = fields


class DisputeCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=Dispute.Reason.choices)
    description = serializers.CharField(max_length=4000, trim_whitespace=True)
    evidence_urls = serializers.ListField(
        child=serializers.URLField(validators=[URLValidator(schemes=["https"])]),
        required=False,
        max_length=5,
    )

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
            evidence=[
                {"author": request.user.username, "message": self.validated_data["description"], "source": "dispute"},
                *[{"author": request.user.username, "image_url": url, "source": "photo"} for url in self.validated_data.get("evidence_urls", [])],
            ],
            private_evidence=[
                {"author": request.user.username, "message": self.validated_data["description"], "source": "private_dispute"},
                *[{"author": request.user.username, "image_url": url, "source": "photo"} for url in self.validated_data.get("evidence_urls", [])],
            ],
            case_history=[{"actor": request.user.username, "status": "open", "at": timezone.now().isoformat()}],
        )
        DisputeMessage.objects.create(
            dispute=dispute,
            author=request.user,
            body=self.validated_data["description"],
            evidence=[{"image_url": url} for url in self.validated_data.get("evidence_urls", [])],
        )
        order.status = Order.Status.DISPUTED
        order.save(update_fields=["status"])
        return dispute


class DisputeMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, trim_whitespace=True)
    evidence_urls = serializers.ListField(
        child=serializers.URLField(validators=[URLValidator(schemes=["https"])]),
        required=False,
        max_length=5,
    )


class MessageReportSerializer(serializers.ModelSerializer):
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)
    reported_user_id = serializers.UUIDField(read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    message_data = serializers.SerializerMethodField()
    reported_user_is_suspended = serializers.SerializerMethodField()

    class Meta:
        model = MessageReport
        fields = [
            "id", "message", "conversation", "reporter", "reporter_username",
            "reported_user", "reported_user_id", "reported_username", "reported_user_is_suspended", "message_data",
            "reason", "reason_display", "description", "status", "status_display",
            "review_notes", "reviewed_by", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_message_data(self, obj):
        if obj.message_id and not obj.message.is_deleted_for_all:
            message = obj.message
            return {
                "content": message.content,
                "image_url": message.image_url,
                "voice_url": message.voice_url,
                "location_lat": message.location_lat,
                "location_lng": message.location_lng,
            }
        return obj.message_snapshot

    def get_reported_user_is_suspended(self, obj):
        return bool(obj.reported_user and obj.reported_user.is_suspended)


class MessageReportCreateSerializer(serializers.Serializer):
    message_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=MessageReport.Reason.choices)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000, trim_whitespace=True)

    def validate_message_id(self, value):
        request = self.context["request"]
        try:
            message = Message.objects.select_related("conversation", "sender").get(pk=value)
        except Message.DoesNotExist as exc:
            raise serializers.ValidationError("Message introuvable.") from exc

        if message.sender_id == request.user.id:
            raise serializers.ValidationError("Vous ne pouvez pas signaler votre propre message.")
        if not message.conversation.participants.filter(user=request.user).exists():
            raise serializers.ValidationError("Ce message ne fait pas partie de vos conversations.")
        if message.is_deleted_for_all:
            raise serializers.ValidationError("Ce message a déjà été supprimé.")
        if MessageReport.objects.filter(
            message=message,
            reporter=request.user,
            status__in=[MessageReport.Status.NEW, MessageReport.Status.UNDER_REVIEW, MessageReport.Status.VALID],
        ).exists():
            raise serializers.ValidationError("Vous avez déjà signalé ce message pour un dossier actif.")

        self.message = message
        return value

    def save(self):
        message = self.message
        return MessageReport.objects.create(
            message=message,
            conversation=message.conversation,
            reporter=self.context["request"].user,
            reported_user=message.sender,
            reported_username=message.sender.username,
            message_snapshot={
                "content": message.content,
                "image_url": message.image_url,
                "voice_url": message.voice_url,
                "location_lat": message.location_lat,
                "location_lng": message.location_lng,
            },
            reason=self.validated_data["reason"],
            description=self.validated_data.get("description", ""),
        )


class AccountModerationActionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AccountModerationAction
        fields = ["id", "target_user", "actor", "actor_username", "action", "reason", "created_at"]
        read_only_fields = fields


class ModeratedAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_suspended", "suspension_reason", "suspended_at"]
        read_only_fields = fields
