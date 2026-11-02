from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase


class PaymentModeTests(APITestCase):
    @override_settings(PAYMENTS_MODE="cash")
    def test_public_config_reports_cash_and_mobile_money_coming_soon(self):
        response = self.client.get(reverse("payments:config"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"mode": "cash", "mobile_money_coming_soon": True},
        )

    @override_settings(PAYMENTS_MODE="cash")
    def test_online_initiation_and_webhook_are_blocked_in_cash_mode(self):
        user = get_user_model().objects.create_user(
            email="cash-buyer@example.com",
            phone_number="+243900000001",
            username="cash-buyer",
            password="password123",
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(reverse("payments:initiate"), {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Le paiement en ligne n'est pas encore disponible.",
        )

        response = self.client.post(reverse("payments:webhook-confirm"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Le paiement en ligne n'est pas encore disponible.",
        )
