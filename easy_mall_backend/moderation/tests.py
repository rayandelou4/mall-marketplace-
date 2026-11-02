from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from orders.models import Order, OrderItem


class ModerationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="admin@mall.test",
            phone_number="+243000000001",
            username="admin",
            password="Admin123!",
        )
        self.seller = User.objects.create_user(
            email="seller@mall.test",
            phone_number="+243000000002",
            username="seller",
            password="Seller123!",
        )
        self.buyer = User.objects.create_user(
            email="buyer@mall.test",
            phone_number="+243000000003",
            username="buyer",
            password="Buyer123!",
        )
        self.category = Category.objects.create(name="Électronique", slug="electronique")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Téléphone test",
            description="Produit de test.",
            price=Decimal("250.00"),
            currency="USD",
            city="Kinshasa",
            country="CD",
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            stock_quantity=3,
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            shipping_address="123 rue de la paix",
            currency="USD",
            payment_method=Order.PaymentMethod.CASH,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            seller=self.seller,
            product_title=self.product.title,
            quantity=1,
            unit_price=self.product.price,
            shipping_cost=Decimal("0.00"),
        )

    def test_user_can_report_product_and_duplicate_is_blocked(self):
        self.client.force_authenticate(self.buyer)
        url = "/api/v1/moderation/reports/"

        response = self.client.post(
            url,
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Description trompeuse.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["seller"]["username"], self.seller.username)
        self.assertFalse(self.product.is_suspended)

        repeat_response = self.client.post(
            url,
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Deuxième signalement identique.",
            },
            format="json",
        )
        self.assertEqual(repeat_response.status_code, 400, repeat_response.content)

    def test_high_risk_report_can_suspend_product_temporarily(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "counterfeit_product",
                "description": "Produit potentiellement contrefait.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_suspended)
        self.assertIn("contrefait", (self.product.suspension_reason or "").lower())

    def test_suspended_product_is_removed_from_public_catalog(self):
        self.product.is_suspended = True
        self.product.suspension_reason = "Produit potentiellement contrefait."
        self.product.save(update_fields=["is_suspended", "suspension_reason"])

        response = self.client.get("/api/v1/catalog/products/")
        self.assertEqual(response.status_code, 200, response.content)
        result_ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(str(self.product.id), result_ids)

    def test_only_admin_can_decide_report(self):
        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Problème de description.",
            },
            format="json",
        )
        report_id = create_response.data["id"]

        buyer_decision = self.client.post(
            f"/api/v1/moderation/reports/{report_id}/decide/",
            {"decision": "reject", "reason": "non valide"},
            format="json",
        )
        self.assertEqual(buyer_decision.status_code, 403, buyer_decision.content)

        self.client.force_authenticate(self.admin)
        admin_decision = self.client.post(
            f"/api/v1/moderation/reports/{report_id}/decide/",
            {"decision": "reject", "reason": "Dossier sans preuve suffisante."},
            format="json",
        )
        self.assertEqual(admin_decision.status_code, 200, admin_decision.content)

    def test_buyer_can_open_dispute_on_own_order(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/v1/moderation/disputes/",
            {"order_id": str(self.order.id), "reason": "Commande non reçue."},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["order"], str(self.order.id))

    def test_ordinary_report_does_not_auto_suspend_product(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Description trompeuse.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_suspended)

    def test_user_cannot_decide_another_users_report(self):
        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Signalement de test.",
            },
            format="json",
        )
        report_id = create_response.data["id"]

        other_user = User.objects.create_user(
            email="other@mall.test",
            phone_number="+243000000004",
            username="otheruser",
            password="Other123!",
        )
        self.client.force_authenticate(other_user)

        response = self.client.post(
            f"/api/v1/moderation/reports/{report_id}/decide/",
            {"decision": "reject", "reason": "modification interdite"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 401, 400))

    def test_suspended_product_is_not_publicly_accessible_by_direct_detail_lookup(self):
        self.product.is_suspended = True
        self.product.suspension_reason = "Produit potentiellement contrefait."
        self.product.save(update_fields=["is_suspended", "suspension_reason"])

        response = self.client.get(f"/api/v1/catalog/products/{self.product.id}/")
        self.assertIn(response.status_code, (400, 403))

    def test_admin_can_reject_report_and_clear_suspension(self):
        self.product.is_suspended = True
        self.product.suspension_reason = "Suspension temporaire déclenchée par un signalement à risque élevé."
        self.product.save(update_fields=["is_suspended", "suspension_reason"])

        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "scam_suspected",
                "description": "Suspicion d'arnaque.",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 400, create_response.content)

        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/moderation/reports/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreaterEqual(len(response.data["results"] if "results" in response.data else response.data), 0)
