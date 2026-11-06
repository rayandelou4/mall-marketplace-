"""
Serializers de l'app `messaging`.
"""

import json

from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from django.db import transaction

from accounts.models import User
from catalog.models import Product

from .models import Conversation, ConversationParticipant, Message


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_avatar_url = serializers.URLField(source="sender.avatar_url", read_only=True, allow_null=True)
    content = serializers.SerializerMethodField()
    reply_to_content = serializers.SerializerMethodField()
    reply_to_sender_username = serializers.CharField(source="reply_to.sender.username", read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = [
            "id", "sender_username", "sender_avatar_url", "content", "image_url", "voice_url",
            "location_lat", "location_lng", "is_read", "is_deleted_for_all", "created_at",
            "edited_at", "reply_to", "reply_to_content", "reply_to_sender_username",
        ]
        read_only_fields = fields

    def get_content(self, obj):
        return "Ce message a été supprimé" if obj.is_deleted_for_all else obj.content

    def get_reply_to_content(self, obj):
        if not obj.reply_to_id:
            return None
        if obj.reply_to.is_deleted_for_all:
            return "Ce message a été supprimé"
        return obj.reply_to.content or ("Message vocal" if obj.reply_to.voice_url else "") or ("Image" if obj.reply_to.image_url else "")


def message_channel_payload(message):
    return json.loads(JSONRenderer().render(MessageSerializer(message).data))


class ConversationSerializer(serializers.ModelSerializer):
    """
    Champs calculés à la volée (pas de dénormalisation) : simple à ce volume,
    à optimiser (select_related/prefetch_related) si le nombre de
    conversations par utilisateur devient important.
    """

    products = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    product_title = serializers.SerializerMethodField()
    other_username = serializers.SerializerMethodField()
    other_avatar_url = serializers.SerializerMethodField()
    other_phone_number = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "product", "product_title", "products", "other_username", "other_avatar_url", "other_phone_number", "last_message", "unread_count", "updated_at"]

    def get_products(self, obj):
        return [{"id": product.id, "title": product.title} for product in obj.products.all().order_by("title")]

    def get_product(self, obj):
        product = obj.products.all().order_by("title").first()
        return product.id if product else None

    def get_product_title(self, obj):
        product = obj.products.all().order_by("title").first()
        return product.title if product else None

    def get_other_username(self, obj):
        request = self.context.get("request")
        other = obj.participants.exclude(user=request.user).select_related("user").first()
        return other.user.username if other else None

    def get_other_avatar_url(self, obj):
        request = self.context.get("request")
        other = obj.participants.exclude(user=request.user).select_related("user").first()
        return other.user.avatar_url if other else None

    def get_other_phone_number(self, obj):
        request = self.context.get("request")
        other = obj.participants.exclude(user=request.user).select_related("user").first()
        return other.user.phone_number if other else None

    def get_last_message(self, obj):
        request = self.context.get("request")
        messages = obj.messages.all()
        if request:
            messages = messages.exclude(hidden_for=request.user)
        last = messages.order_by("-created_at").first()
        if not last:
            return None
        if last.is_deleted_for_all:
            preview = "Ce message a été supprimé"
        else:
            preview = (
                last.content
                or ("Message vocal" if last.voice_url else "")
                or ("Image" if last.image_url else "")
                or ("Position partagée" if last.location_lat is not None else "")
            )
        return {
            "content": preview,
            "created_at": last.created_at,
            "sender_username": last.sender.username,
        }

    def get_unread_count(self, obj):
        request = self.context.get("request")
        return obj.messages.filter(is_read=False).exclude(sender=request.user).exclude(hidden_for=request.user).count()


class ConversationStartSerializer(serializers.Serializer):
    """Démarre une conversation (ou réutilise une existante) et y poste le premier message."""

    recipient_username = serializers.CharField()
    product_id = serializers.UUIDField(required=False, allow_null=True)
    content = serializers.CharField()

    def validate_recipient_username(self, value):
        request = self.context["request"]
        try:
            recipient = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable.")
        if not recipient.is_active or recipient.is_suspended:
            raise serializers.ValidationError("Cet utilisateur ne peut pas recevoir de messages pour le moment.")
        if recipient == request.user:
            raise serializers.ValidationError("Impossible de démarrer une conversation avec vous-même.")
        self.recipient = recipient
        return value

    def validate_product_id(self, value):
        if not value:
            return value
        try:
            product = Product.objects.only("seller_id").get(pk=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Produit introuvable.")
        if product.seller_id != self.recipient.pk:
            raise serializers.ValidationError("Ce produit n'appartient pas à l'utilisateur destinataire.")
        return value

    def save(self):
        request = self.context["request"]
        product_id = self.validated_data.get("product_id")

        with transaction.atomic():
            # Lock both users in a stable order so simultaneous starts for the same pair serialize.
            list(
                User.objects.select_for_update()
                .filter(pk__in=[request.user.pk, self.recipient.pk])
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            participant_pair_key = ":".join(sorted([str(request.user.pk), str(self.recipient.pk)]))
            conversation, created = Conversation.objects.get_or_create(
                participant_pair_key=participant_pair_key
            )
            if created:
                ConversationParticipant.objects.bulk_create(
                    [
                        ConversationParticipant(conversation=conversation, user=request.user),
                        ConversationParticipant(conversation=conversation, user=self.recipient),
                    ]
                )
            if product_id:
                conversation.products.add(Product.objects.get(pk=product_id))

            self.message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=self.validated_data["content"],
            )
            conversation.participants.update(is_hidden=False)
            conversation.save()  # touche updated_at (auto_now) pour remonter la conversation en tête de liste
        return conversation


class MessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    image_url = serializers.URLField(required=False, allow_null=True)
    voice_url = serializers.URLField(required=False, allow_null=True)
    location_lat = serializers.FloatField(required=False, allow_null=True)
    location_lng = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("content") and not attrs.get("image_url") and not attrs.get("voice_url") and attrs.get("location_lat") is None:
            raise serializers.ValidationError("Le message doit contenir du texte, une image ou une localisation.")
        reply_to_id = attrs.get("reply_to_id")
        if reply_to_id:
            try:
                attrs["reply_to"] = Message.objects.get(pk=reply_to_id, conversation=self.context["conversation"])
            except Message.DoesNotExist:
                raise serializers.ValidationError({"reply_to_id": "Message de réponse introuvable dans cette conversation."})
            attrs.pop("reply_to_id")
        return attrs

    def save(self):
        conversation = self.context["conversation"]
        request = self.context["request"]
        message = Message.objects.create(conversation=conversation, sender=request.user, **self.validated_data)
        conversation.participants.update(is_hidden=False)
        conversation.save()
        return message
