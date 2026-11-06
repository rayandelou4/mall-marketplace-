"""
Vues de l'app `messaging`.

Les endpoints HTTP gèrent l'historique et l'envoi confirmé ; les nouveaux
messages et changements d'état sont diffusés via Django Channels. Le frontend
utilise aussi un polling de secours si le WebSocket est indisponible.
"""

import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    ConversationStartSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    message_channel_payload,
)

logger = logging.getLogger(__name__)


class ActiveAccountPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and not request.user.is_suspended


def broadcast_message(conversation, message):
    async_to_sync(get_channel_layer().group_send)(
        f"conversation_{conversation.id}",
        {"type": "chat_message", "message": message_channel_payload(message)},
    )


def upload_voice_file(uploaded_file):
    import cloudinary

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    result = cloudinary.uploader.upload(
        uploaded_file,
        resource_type="video",
        folder="easy_mall/voices",
        public_id=uuid.uuid4().hex,
        overwrite=False,
    )
    return result["secure_url"]


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [ActiveAccountPermission]
    throttle_classes = [ScopedRateThrottle]

    def get_queryset(self):
        if self.action == "list":
            queryset = Conversation.objects.filter(
                participants__user=self.request.user,
                participants__is_hidden=False,
            )
        else:
            queryset = Conversation.objects.filter(participants__user=self.request.user)
        return queryset.distinct()

    def get_throttles(self):
        if getattr(self, "action", None) == "start":
            self.throttle_scope = "conversation_start"
        elif getattr(self, "action", None) == "messages" and self.request.method == "POST":
            self.throttle_scope = "message_send"
        return super().get_throttles()

    @action(detail=False, methods=["post"])
    def start(self, request):
        serializer = ConversationStartSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save()
        broadcast_message(conversation, serializer.message)
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path="hide")
    def hide(self, request, pk=None):
        conversation = self.get_object()
        conversation.participants.filter(user=request.user).update(is_hidden=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post", "delete"])
    def messages(self, request, pk=None):
        conversation = self.get_object()

        if request.method == "DELETE":
            message_id = request.query_params.get("message_id")
            scope = request.query_params.get("scope", "me")
            if not message_id:
                return Response({"detail": "message_id est requis."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                message = conversation.messages.get(pk=message_id)
            except Message.DoesNotExist:
                return Response({"detail": "Message introuvable."}, status=status.HTTP_404_NOT_FOUND)
            if scope == "all":
                if message.sender_id != request.user.id:
                    return Response({"detail": "Seul l'auteur peut supprimer ce message pour tous."}, status=status.HTTP_403_FORBIDDEN)
                message.is_deleted_for_all = True
                message.content = ""
                message.image_url = None
                message.voice_url = None
                message.location_lat = None
                message.location_lng = None
                message.save(update_fields=["is_deleted_for_all", "content", "image_url", "voice_url", "location_lat", "location_lng"])
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"conversation_{conversation.id}",
                    {"type": "message_deleted", "message_id": str(message.id), "scope": "all"},
                )
            else:
                message.hidden_for.add(request.user)
                async_to_sync(get_channel_layer().group_send)(
                    f"conversation_{conversation.id}",
                    {
                        "type": "messages_hidden",
                        "message_ids": [str(message.id)],
                        "user_id": str(request.user.id),
                    },
                )
            return Response(status=status.HTTP_204_NO_CONTENT)

        if request.method == "POST":
            data = request.data
            voice_file = request.FILES.get("voice")
            if voice_file:
                if voice_file.size > 12 * 1024 * 1024:
                    return Response(
                        {"detail": "Le message vocal dépasse la limite de 12 Mo."},
                        status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
                if not (voice_file.content_type or "").startswith("audio/"):
                    return Response(
                        {"detail": "Le fichier transmis n'est pas un enregistrement audio valide."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not all((settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET)):
                    return Response(
                        {"detail": "Le stockage des messages vocaux n'est pas configuré sur le serveur."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                try:
                    voice_url = upload_voice_file(voice_file)
                except Exception:
                    logger.exception("Cloudinary voice upload failed")
                    return Response(
                        {"detail": "Le message vocal n'a pas pu être enregistré. Réessayez dans quelques instants."},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )
                data = request.data.copy()
                data.pop("voice", None)
                data["voice_url"] = voice_url

            serializer = MessageCreateSerializer(
                data=data, context={"request": request, "conversation": conversation}
            )
            serializer.is_valid(raise_exception=True)
            message = serializer.save()
            message_data = MessageSerializer(message).data
            broadcast_message(conversation, message)
            return Response(message_data, status=status.HTTP_201_CREATED)

        # GET : validate pagination, mark messages read, then return newest page first.
        page = request.query_params.get("page", "1")
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            return Response({"detail": "Le numéro de page doit être un entier positif."}, status=status.HTTP_400_BAD_REQUEST)

        unread_messages = (
            Message.objects.filter(conversation=conversation, is_read=False)
            .exclude(sender=request.user)
            .exclude(hidden_for=request.user)
        )
        unread_message_ids = [str(message_id) for message_id in unread_messages.values_list("pk", flat=True)]
        if unread_message_ids:
            unread_messages.update(is_read=True)
            async_to_sync(get_channel_layer().group_send)(
                f"conversation_{conversation.id}",
                {
                    "type": "messages_read",
                    "message_ids": unread_message_ids,
                    "reader_username": request.user.username,
                },
            )
        page_size = 40
        queryset = conversation.messages.select_related("sender", "reply_to", "reply_to__sender").exclude(hidden_for=request.user)
        total = queryset.count()
        offset = (page - 1) * page_size
        page_messages = list(queryset.order_by("-created_at", "-id")[offset:offset + page_size])
        page_messages.reverse()
        return Response({
            "results": MessageSerializer(page_messages, many=True).data,
            "page": page,
            "has_more": offset + len(page_messages) < total,
        })

    @action(detail=True, methods=["patch"], url_path=r"messages/(?P<message_id>[^/.]+)")
    def edit_message(self, request, pk=None, message_id=None):
        conversation = self.get_object()
        try:
            message = conversation.messages.get(pk=message_id, sender=request.user)
        except Message.DoesNotExist:
            return Response({"detail": "Message introuvable ou non modifiable."}, status=status.HTTP_404_NOT_FOUND)
        if message.is_deleted_for_all:
            return Response({"detail": "Un message supprimé ne peut pas être modifié."}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() >= message.created_at + timedelta(minutes=5):
            return Response(
                {"detail": "La modification n'est possible que pendant les 5 minutes suivant l'envoi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content = request.data.get("content")
        if not isinstance(content, str) or not content.strip():
            return Response({"content": ["Le message ne peut pas être vide."]}, status=status.HTTP_400_BAD_REQUEST)
        message.content = content.strip()
        message.edited_at = timezone.now()
        message.save(update_fields=["content", "edited_at"])
        async_to_sync(get_channel_layer().group_send)(
            f"conversation_{conversation.id}",
            {"type": "message_updated", "message": message_channel_payload(message)},
        )
        return Response(MessageSerializer(message).data)

    @action(detail=True, methods=["post"], url_path="messages/clear")
    def clear_messages(self, request, pk=None):
        conversation = self.get_object()
        message_ids = list(conversation.messages.exclude(hidden_for=request.user).values_list("id", flat=True))
        for message in conversation.messages.filter(id__in=message_ids):
            message.hidden_for.add(request.user)
        if message_ids:
            async_to_sync(get_channel_layer().group_send)(
                f"conversation_{conversation.id}",
                {
                    "type": "messages_hidden",
                    "message_ids": [str(message_id) for message_id in message_ids],
                    "user_id": str(request.user.id),
                },
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
