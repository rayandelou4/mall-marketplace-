"""
Consumer WebSocket pour le chat temps réel (Django Channels).

Remplace le polling HTTP (l'ancien `GET .../messages/` interrogé toutes les
4s côté frontend) par une connexion persistante : un message envoyé par un
participant est diffusé instantanément à l'autre. L'historique au chargement
d'une conversation reste chargé via l'endpoint REST existant (`messages`,
GET) — le WebSocket ne porte que les nouveaux messages à partir de la connexion.
"""

import json
import math
import time
from uuid import UUID
from urllib.parse import urlsplit

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from django.core.exceptions import ValidationError

from accounts.models import User
from .models import Conversation, Message
from .serializers import message_channel_payload


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"
        user = self.scope.get("user")

        if user is None or not user.is_authenticated or not user.is_active or user.is_suspended:
            await self.close(code=4001)  # non authentifié
            return

        if not await self._is_participant(user):
            await self.close(code=4003)  # authentifié mais pas participant de cette conversation
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Ouvrir le fil marque les messages reçus comme lus (même règle que côté REST).
        message_ids = await self._mark_as_read(user)
        if message_ids:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "messages_read",
                    "message_ids": message_ids,
                    "reader_username": user.username,
                },
            )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        user = self.scope["user"]
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            await self._send_message_error("Le format du message est invalide.")
            return

        if not await self._account_can_message(user.pk):
            await self._send_message_error("Votre compte ne peut pas envoyer de messages actuellement.")
            return
        if not isinstance(payload, dict):
            await self._send_message_error("Le format du message est invalide.")
            return

        if await self._is_rate_limited(user.pk):
            await self.send(text_data=json.dumps({
                "type": "rate_limited",
                "detail": "Vous envoyez des messages trop rapidement. Réessayez dans une minute.",
            }))
            return

        content = payload.get("content", "")
        image_url = payload.get("image_url")
        voice_url = payload.get("voice_url")
        location_lat = payload.get("location_lat")
        location_lng = payload.get("location_lng")
        reply_to_id = payload.get("reply_to_id")

        if not isinstance(content, str) or len(content) > 5000:
            await self._send_message_error("Le texte du message est invalide.")
            return
        for value in (image_url, voice_url):
            if value is not None and not self._is_valid_url(value):
                await self._send_message_error("L'URL du média est invalide.")
                return
        if (location_lat is None) != (location_lng is None):
            await self._send_message_error("La localisation doit contenir latitude et longitude.")
            return
        if location_lat is not None and (
            isinstance(location_lat, bool)
            or isinstance(location_lng, bool)
            or not isinstance(location_lat, (int, float))
            or not isinstance(location_lng, (int, float))
            or not math.isfinite(location_lat)
            or not math.isfinite(location_lng)
            or not -90 <= location_lat <= 90
            or not -180 <= location_lng <= 180
        ):
            await self._send_message_error("Les coordonnées de localisation sont invalides.")
            return
        if reply_to_id is not None:
            try:
                reply_to_id = str(UUID(str(reply_to_id)))
            except (ValueError, TypeError, AttributeError):
                await self._send_message_error("L'identifiant du message de réponse est invalide.")
                return

        if not content and not image_url and not voice_url and location_lat is None:
            await self._send_message_error("Le message doit contenir du texte ou un média.")
            return

        message_data = await self._create_message(
            user, content, image_url, voice_url, location_lat, location_lng, reply_to_id
        )
        if message_data is None:
            await self._send_message_error("Le message auquel vous répondez est introuvable dans cette conversation.")
            return

        await self.channel_layer.group_send(
            self.group_name, {"type": "chat_message", "message": message_data}
        )

    async def chat_message(self, event):
        """Relaie aux participants un message diffusé sur le groupe (y compris à l'expéditeur)."""
        message = event["message"]
        user = self.scope["user"]
        if message["sender_username"] != user.username:
            if await self._mark_message_read(message["id"], user):
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "messages_read",
                        "message_ids": [message["id"]],
                        "reader_username": user.username,
                    },
                )
        await self.send(text_data=json.dumps(message))

    async def messages_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "messages_read",
            "message_ids": event["message_ids"],
            "reader_username": event["reader_username"],
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"],
            "scope": event["scope"],
        }))

    async def messages_hidden(self, event):
        await self.send(text_data=json.dumps({
            "type": "messages_hidden",
            "message_ids": event["message_ids"],
            "user_id": event["user_id"],
        }))

    async def message_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_updated",
            "message": event["message"],
        }))

    async def message_error(self, event):
        await self.send(text_data=json.dumps({"type": "message_error", "detail": event["detail"]}))

    async def _send_message_error(self, detail):
        await self.send(text_data=json.dumps({"type": "message_error", "detail": detail}))

    @database_sync_to_async
    def _is_rate_limited(self, user_id):
        minute_bucket = int(time.time() // 60)
        key = f"messaging:ws-rate:{user_id}:{minute_bucket}"
        cache.add(key, 0, timeout=120)
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=120)
            count = 1
        return count > 30

    @database_sync_to_async
    def _is_participant(self, user):
        try:
            return Conversation.objects.filter(pk=self.conversation_id, participants__user=user).exists()
        except (ValueError, ValidationError):
            return False  # conversation_id n'est même pas un UUID valide

    @database_sync_to_async
    def _account_can_message(self, user_id):
        return User.objects.filter(pk=user_id, is_active=True, is_suspended=False).exists()

    @database_sync_to_async
    def _mark_as_read(self, user):
        unread = (
            Message.objects.filter(conversation_id=self.conversation_id, is_read=False)
            .exclude(sender=user)
            .exclude(hidden_for=user)
        )
        message_ids = [str(message_id) for message_id in unread.values_list("pk", flat=True)]
        unread.update(is_read=True)
        return message_ids

    @database_sync_to_async
    def _mark_message_read(self, message_id, user):
        return Message.objects.filter(
            pk=message_id,
            conversation_id=self.conversation_id,
            is_read=False,
        ).exclude(sender=user).exclude(hidden_for=user).update(is_read=True) > 0

    @database_sync_to_async
    def _create_message(self, user, content, image_url, voice_url, location_lat, location_lng, reply_to_id=None):
        reply_to = None
        if reply_to_id:
            reply_to = Message.objects.filter(pk=reply_to_id, conversation_id=self.conversation_id).first()
            if reply_to is None:
                return None
        message = Message.objects.create(
            conversation_id=self.conversation_id,
            sender=user,
            content=content or "",
            image_url=image_url,
            voice_url=voice_url,
            location_lat=location_lat,
            location_lng=location_lng,
            reply_to=reply_to,
        )
        # updated_at (auto_now) n'est appliqué que par .save() — ce .update()
        # bulk doit donc fixer la valeur explicitement pour remonter la
        # conversation en tête de liste, comme le fait déjà le flux REST.
        Conversation.objects.filter(pk=self.conversation_id).update(updated_at=message.created_at)
        conversation = Conversation.objects.get(pk=self.conversation_id)
        conversation.participants.update(is_hidden=False)
        return message_channel_payload(message)

    @staticmethod
    def _is_valid_url(value):
        if not isinstance(value, str) or len(value) > 2000:
            return False
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
