from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product


class FakeBuyerAssistantProvider:
    def __init__(self, ranked=None):
        self.ranked = ranked

    def understand_needs(self, *, message, categories):
        return {
            "max_price": "350.00",
            "currency": "USD",
            "keywords": ["portable"],
            "important_features": ["études"],
        }

    def rank_candidates(self, *, message, criteria, candidates):
        return self.ranked if self.ranked is not None else [item["id"] for item in candidates]


class BuyerAssistantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            email="assistant-seller@mall.test",
            phone_number="+243900000201",
            username="assistant-seller",
            password="Seller123!",
        )
        self.category = Category.objects.create(name="Ordinateurs")

    def create_product(self, *, title, price, currency="USD", status=Product.Status.PUBLISHED):
        return Product.objects.create(
            seller=self.seller,
            category=self.category,
            title=title,
            description="Ordinateur portable pour cours",
            price=price,
            currency=currency,
            city="Kinshasa",
            country="RDC",
            stock_quantity=2,
            status=status,
            moderation_status=Product.ModerationStatus.APPROVED,
        )

    @override_settings(BUYER_ASSISTANT_PROVIDER="")
    def test_assistant_is_disabled_without_provider(self):
        self.assertFalse(self.client.get("/api/v1/buyer-assistant/config/").data["enabled"])
        response = self.client.post(
            "/api/v1/buyer-assistant/search/",
            {"message": "Ordinateur pour étudier"},
            format="json",
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(BUYER_ASSISTANT_PROVIDER="configured.provider.Class")
    def test_budget_is_server_enforced_and_provider_cannot_inject_products(self):
        affordable = self.create_product(title="Portable abordable", price="300.00")
        self.create_product(title="Portable hors budget", price="500.00")
        self.create_product(title="Portable autre devise", price="100.00", currency="CDF")
        self.create_product(title="Portable brouillon", price="150.00", status=Product.Status.DRAFT)
        fake_id = "00000000-0000-0000-0000-000000000001"
        provider = FakeBuyerAssistantProvider(ranked=[fake_id, str(affordable.pk)])

        with patch("buyer_assistant.views.services.get_provider", return_value=provider):
            response = self.client.post(
                "/api/v1/buyer-assistant/search/",
                {"message": "Portable pour mes études, maximum 350 USD"},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["offers"]), 1)
        offer = response.data["offers"][0]["product"]
        self.assertEqual(offer["id"], str(affordable.pk))
        self.assertEqual(offer["price"], "300.00")
        self.assertEqual(offer["seller_username"], self.seller.username)

    @override_settings(BUYER_ASSISTANT_PROVIDER="configured.provider.Class")
    def test_budget_without_currency_is_rejected(self):
        class InvalidBudgetProvider(FakeBuyerAssistantProvider):
            def understand_needs(self, *, message, categories):
                return {"max_price": "350.00", "currency": ""}

        with patch(
            "buyer_assistant.views.services.get_provider",
            return_value=InvalidBudgetProvider(),
        ):
            response = self.client.post(
                "/api/v1/buyer-assistant/search/",
                {"message": "Portable à moins de 350"},
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("currency", response.data)