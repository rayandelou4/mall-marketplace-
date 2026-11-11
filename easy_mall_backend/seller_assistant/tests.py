from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User


class SellerAssistantApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="assistant-seller@example.com",
            phone_number="+243900000071",
            username="assistant-seller",
            password="Seller123!",
        )
        self.client = APIClient()

    def test_assistant_is_disabled_by_default_and_does_not_process_images(self):
        self.client.force_authenticate(self.user)

        config = self.client.get("/api/v1/seller-assistant/config/")
        response = self.client.post(
            "/api/v1/seller-assistant/suggestions/",
            {"image_urls": ["https://images.example/item.jpg"]},
            format="json",
        )

        self.assertEqual(config.status_code, 200)
        self.assertFalse(config.data["enabled"])
        self.assertEqual(response.status_code, 503)

    def test_assistant_endpoints_require_authentication(self):
        with override_settings(SELLER_ASSISTANT_PROVIDER=""):
            self.assertEqual(
                self.client.get("/api/v1/seller-assistant/config/").status_code, 401
            )
            self.assertEqual(
                self.client.post(
                    "/api/v1/seller-assistant/suggestions/",
                    {"image_urls": ["https://images.example/item.jpg"]},
                    format="json",
                ).status_code,
                401,
            )