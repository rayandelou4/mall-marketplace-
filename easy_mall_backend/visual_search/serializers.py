from rest_framework import serializers


class VisualSearchRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()
    filters = serializers.DictField(required=False, default=dict)

    def validate_image(self, image):
        if image.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("La photo ne peut pas dépasser 8 Mo.")
        return image