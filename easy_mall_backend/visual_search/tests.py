from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User


class VisualSearchApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="visual-search-buyer@example.com",
            phone_number="+243900000081",
            username="visual-search-buyer",
            password="Buyer123!",
        )

    @override_settings(VISUAL_SEARCH_PROVIDER="")
    def test_search_is_disabled_without_a_configured_engine(self):
        client = APIClient()

        config = client.get("/api/v1/visual-search/config/")
        self.assertEqual(
            client.post("/api/v1/visual-search/search/", {}, format="multipart").status_code,
            401,
        )
        client.force_authenticate(self.user)
        response = client.post("/api/v1/visual-search/search/", {}, format="multipart")

        self.assertEqual(config.status_code, 200)
        self.assertFalse(config.data["enabled"])
        self.assertEqual(response.status_code, 503)