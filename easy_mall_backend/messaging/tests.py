from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product

from .models import Conversation, ConversationParticipant
from .serializers import (
    ConversationSerializer,
    ConversationStartSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    message_channel_payload,
)
from .views import ConversationViewSet


class ConversationStartSerializerTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email="sender@example.com",
            phone_number="+10000000001",
            username="sender",
            password="test-password",
        )
        self.recipient = User.objects.create_user(
            email="recipient@example.com",
            phone_number="+10000000002",
            username="recipient",
            password="test-password",
        )
        category = Category.objects.create(name="Test", slug="test")
        self.products = [
            Product.objects.create(
                seller=self.recipient,
                category=category,
                title=title,
                description="Test product",
                price="10.00",
                city="Paris",
                country="France",
            )
            for title in ("Choisi 1", "Choisi 2", "Non choisi")
        ]
        self.request = RequestFactory().post("/messaging/conversations/start/")
        self.request.user = self.sender

    def start(self, product, content):
        serializer = ConversationStartSerializer(
            data={
                "recipient_username": self.recipient.username,
                "product_id": str(product.pk),
                "content": content,
            },
            context={"request": self.request},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_pair_reuses_one_conversation_and_keeps_only_selected_products(self):
        first = self.start(self.products[0], "Bonjour pour le premier produit")
        second = self.start(self.products[1], "Et pour le deuxième ?")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Conversation.objects.count(), 1)
        data = ConversationSerializer(second, context={"request": self.request}).data
        self.assertEqual(data["other_phone_number"], self.recipient.phone_number)
        self.assertEqual(
            {product["id"] for product in data["products"]},
            {self.products[0].pk, self.products[1].pk},
        )

    def test_start_rejects_product_owned_by_another_user(self):
        serializer = ConversationStartSerializer(
            data={
                "recipient_username": self.sender.username,
                "product_id": str(self.products[0].pk),
                "content": "Bonjour",
            },
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("product_id", serializer.errors)

    def test_hidden_conversation_is_not_returned_in_own_list(self):
        conversation = self.start(self.products[0], "Bonjour")
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user=self.sender,
        ).update(is_hidden=True)

        view = ConversationViewSet()
        view.request = SimpleNamespace(user=self.sender)
        view.action = "list"

        self.assertFalse(view.get_queryset().filter(pk=conversation.pk).exists())

    def test_voice_message_can_be_created_and_serialized_without_text(self):
        conversation = self.start(self.products[0], "Bonjour")
        voice_url = "https://res.cloudinary.com/example/video/upload/voice.webm"
        serializer = MessageCreateSerializer(
            data={"voice_url": voice_url},
            context={"request": self.request, "conversation": conversation},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        message = serializer.save()

        serialized = MessageSerializer(message).data
        self.assertEqual(serialized["voice_url"], voice_url)
        self.assertIn("is_deleted_for_all", serialized)
        self.assertFalse(serialized["is_deleted_for_all"])
        self.assertEqual(
            ConversationSerializer(conversation, context={"request": self.request}).data["last_message"]["content"],
            "Message vocal",
        )

    @patch("messaging.views.broadcast_message")
    def test_rest_message_is_broadcast_to_conversation(self, broadcast):
        conversation = self.start(self.products[0], "Bonjour")
        client = APIClient()
        client.force_authenticate(self.sender)

        response = client.post(
            reverse("messaging:conversation-messages", kwargs={"pk": conversation.pk}),
            {"content": "Message envoyé par HTTP"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[0].pk, conversation.pk)
        self.assertEqual(broadcast.call_args.args[1].content, "Message envoyé par HTTP")

    def test_message_channel_payload_is_json_safe(self):
        conversation = self.start(self.products[0], "Message à diffuser")
        message = conversation.messages.latest("created_at")

        payload = message_channel_payload(message)

        self.assertIsInstance(payload["id"], str)
        self.assertIsInstance(payload["created_at"], str)
        self.assertEqual(payload["content"], "Message à diffuser")

    @patch("messaging.views.broadcast_message")
    @patch("messaging.views.upload_voice_file", return_value="https://res.cloudinary.com/example/video/upload/voice.webm")
    @override_settings(
        CLOUDINARY_CLOUD_NAME="example",
        CLOUDINARY_API_KEY="test-key",
        CLOUDINARY_API_SECRET="test-secret",
    )
    def test_multipart_voice_is_uploaded_and_broadcast(self, upload_voice, broadcast):
        conversation = self.start(self.products[0], "Bonjour")
        client = APIClient()
        client.force_authenticate(self.sender)

        response = client.post(
            reverse("messaging:conversation-messages", kwargs={"pk": conversation.pk}),
            {"voice": SimpleUploadedFile("voice.webm", b"audio-data", content_type="audio/webm")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["voice_url"], "https://res.cloudinary.com/example/video/upload/voice.webm")
        upload_voice.assert_called_once()
        broadcast.assert_called_once()