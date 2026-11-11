from rest_framework import serializers

from catalog.models import Product


class AssistantQuerySerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1200, trim_whitespace=True)


class BuyerCriteriaSerializer(serializers.Serializer):
    max_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    condition = serializers.ChoiceField(
        choices=Product.Condition.choices, required=False, allow_blank=True
    )
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, max_length=10
    )
    important_features = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, max_length=8
    )

    def validate(self, attrs):
        if attrs.get("max_price") is not None and not attrs.get("currency", "").strip():
            raise serializers.ValidationError(
                {"currency": "La devise est nécessaire pour appliquer le budget."}
            )
        if attrs.get("currency"):
            attrs["currency"] = attrs["currency"].strip().upper()
        return attrs