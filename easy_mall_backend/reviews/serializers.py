"""
Serializers de l'app `reviews`.
"""

from django.db.models import Avg
from rest_framework import serializers

from accounts.models import User
from orders.models import Order

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True)
    product_title = serializers.CharField(source="product.title", read_only=True, default=None)

    class Meta:
        model = Review
        fields = ["id", "reviewer_username", "product_title", "rating", "comment", "created_at"]
        read_only_fields = fields


def _recalculate_average_rating(user):
    avg = Review.objects.filter(
        reviewed_user=user, moderation_status=Review.ModerationStatus.APPROVED
    ).aggregate(Avg("rating"))["rating__avg"]
    user.average_rating = round(avg, 2) if avg is not None else 0
    user.save(update_fields=["average_rating"])


class ReviewCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    reviewed_username = serializers.CharField()
    product_id = serializers.UUIDField(required=False, allow_null=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]

        try:
            order = Order.objects.get(pk=attrs["order_id"], buyer=request.user)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Commande introuvable.")
        if order.status != Order.Status.DELIVERED:
            raise serializers.ValidationError(
                "Un avis ne peut être laissé qu'après confirmation de réception de la commande."
            )

        try:
            reviewed_user = User.objects.get(username=attrs["reviewed_username"])
        except User.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable.")

        if not order.items.filter(seller=reviewed_user).exists():
            raise serializers.ValidationError("Cet utilisateur n'est pas vendeur sur cette commande.")

        if Review.objects.filter(reviewer=request.user, order=order, reviewed_user=reviewed_user).exists():
            raise serializers.ValidationError("Vous avez déjà laissé un avis pour ce vendeur sur cette commande.")

        attrs["order"] = order
        attrs["reviewed_user"] = reviewed_user
        return attrs

    def save(self):
        request = self.context["request"]
        review = Review.objects.create(
            reviewer=request.user,
            reviewed_user=self.validated_data["reviewed_user"],
            order=self.validated_data["order"],
            product_id=self.validated_data.get("product_id"),
            rating=self.validated_data["rating"],
            comment=self.validated_data.get("comment", ""),
        )
        _recalculate_average_rating(review.reviewed_user)
        return review
