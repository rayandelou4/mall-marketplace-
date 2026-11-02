"""
Modèles de l'app `messaging`.

Chat entre un acheteur et un vendeur, éventuellement rattaché à un produit.
Les messages sont persistés en base, diffusés via Django Channels/WebSocket,
et récupérés par HTTP pour l'historique et lorsque la connexion temps réel
n'est pas disponible.
"""

import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant_pair_key = models.CharField(max_length=73, null=True, unique=True, editable=False)
    products = models.ManyToManyField(
        "catalog.Product", blank=True, related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # "Touché" (auto_now) à chaque nouveau message pour trier la liste par activité récente.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.id}"


class ConversationParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships"
    )
    is_hidden = models.BooleanField(default=False)

    class Meta:
        db_table = "conversation_participants"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="unique_conversation_participant")
        ]

    def __str__(self):
        return f"{self.user} — {self.conversation_id}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")

    content = models.TextField(blank=True)
    image_url = models.URLField(blank=True, null=True)
    voice_url = models.URLField(blank=True, null=True)
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    is_deleted_for_all = models.BooleanField(default=False)
    hidden_for = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="hidden_messages",
    )
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender} @ {self.created_at:%d/%m %H:%M}"
