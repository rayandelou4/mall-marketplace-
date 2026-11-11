from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Category

from . import services
from .providers import LISTING_ASSISTANT_INSTRUCTIONS
from .serializers import ListingSuggestionRequestSerializer, ListingSuggestionsSerializer


class AssistantConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"enabled": services.is_configured()})


class ListingSuggestionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not services.is_configured():
            return Response(
                {"detail": "L’assistant vendeur n’est pas configuré."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        request_serializer = ListingSuggestionRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        category_options = list(
            Category.objects.filter(is_active=True)
            .order_by("order", "name")
            .values("id", "name", "parent_id")
        )
        provider = services.get_provider()
        suggestions = provider.suggest_listing(
            image_urls=request_serializer.validated_data["image_urls"],
            current_fields={
                key: value
                for key, value in request_serializer.validated_data.items()
                if key != "image_urls"
            },
            categories=category_options,
            instructions=LISTING_ASSISTANT_INSTRUCTIONS,
        )
        suggestion_serializer = ListingSuggestionsSerializer(data=suggestions)
        suggestion_serializer.is_valid(raise_exception=True)
        return Response(
            {
                **suggestion_serializer.validated_data,
                "disclaimer": (
                    "Suggestions à vérifier et modifier. Les éléments visuels ne confirment "
                    "aucune caractéristique technique invisible."
                ),
            }
        )