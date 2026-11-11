from rest_framework import serializers

from .models import Negotiation, NegotiationEvent


class ProposalInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value="0.01")


class CounterProposalInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value="0.01")


class NegotiationEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source="actor.username", read_only=True, allow_null=True
    )
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = NegotiationEvent
        fields = ["id", "kind", "kind_display", "amount", "actor_username", "created_at"]


class NegotiationSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=12, decimal_places=2, read_only=True
    )
    currency = serializers.CharField(source="product.currency", read_only=True)
    variant_label = serializers.CharField(source="variant.label", read_only=True, allow_null=True)
    buyer_username = serializers.CharField(source="buyer.username", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    events = NegotiationEventSerializer(many=True, read_only=True)
    proposal_count = serializers.SerializerMethodField()
    latest_amount = serializers.SerializerMethodField()
    max_proposals = serializers.SerializerMethodField()

    class Meta:
        model = Negotiation
        fields = [
            "id", "product", "product_title", "product_price", "currency", "variant",
            "variant_label", "buyer", "buyer_username", "seller", "seller_username",
            "status", "accepted_price", "latest_amount", "proposal_count", "max_proposals", "expires_at",
            "reserved_until", "created_at", "updated_at", "events",
        ]
        read_only_fields = fields

    def get_proposal_count(self, obj):
        return obj.events.filter(
            kind__in=[NegotiationEvent.Kind.PROPOSAL, NegotiationEvent.Kind.COUNTER_PROPOSAL]
        ).count()

    def get_latest_amount(self, obj):
        event = obj.events.filter(
            kind__in=[NegotiationEvent.Kind.PROPOSAL, NegotiationEvent.Kind.COUNTER_PROPOSAL]
        ).order_by("-created_at", "-id").first()
        return event.amount if event else None

    def get_max_proposals(self, obj):
        from django.conf import settings

        return settings.NEGOTIATION_MAX_PROPOSALS