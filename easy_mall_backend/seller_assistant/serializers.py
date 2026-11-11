from rest_framework import serializers

from catalog.models import Category


class ListingSuggestionRequestSerializer(serializers.Serializer):
    image_urls = serializers.ListField(
        child=serializers.URLField(schemes=["https"]), min_length=1, max_length=3
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)


class ListingSuggestionsSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    visual_attributes = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, max_length=12
    )
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, max_length=12
    )
    quality_suggestions = serializers.ListField(
        child=serializers.CharField(max_length=240), required=False, max_length=8
    )

    def validate_category_id(self, value):
        if value is not None and not Category.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("La catégorie proposée n'est pas disponible.")
        return value