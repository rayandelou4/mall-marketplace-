"""
Vues de l'app `reviews`.
"""

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        return ReviewCreateSerializer if self.action == "create" else ReviewSerializer

    def get_queryset(self):
        queryset = Review.objects.filter(moderation_status=Review.ModerationStatus.APPROVED).select_related(
            "reviewer", "product"
        )
        username = self.request.query_params.get("user")
        if username:
            queryset = queryset.filter(reviewed_user__username=username)
        product_id = self.request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
