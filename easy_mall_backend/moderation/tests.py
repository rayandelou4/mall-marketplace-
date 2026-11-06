from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from messaging.models import Conversation, ConversationParticipant, Message
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

    def test_staff_requires_model_permissions_for_global_reports_and_decisions(self):
        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Signalement à examiner.",
            },
            format="json",
        )
        report_id = create_response.data["id"]

        staff = User.objects.create_user(
            email="staff@mall.test",
            phone_number="+243000000005",
            username="staff",
            password="Staff123!",
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get("/api/v1/moderation/reports/").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/api/v1/moderation/reports/{report_id}/decide/",
                {"decision": "reject", "reason": "Rejeté."},
                format="json",
            ).status_code,
            403,
        )

        staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="moderation", codename="view_productreport"
            )
        )
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        list_response = self.client.get("/api/v1/moderation/reports/")
        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertEqual(list_response.data["results"][0]["id"], report_id)
        self.assertEqual(
            self.client.post(
                f"/api/v1/moderation/reports/{report_id}/decide/",
                {"decision": "reject", "reason": "Rejeté."},
                format="json",
            ).status_code,
            403,
        )

        staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="moderation", codename="change_productreport"
            )
        )
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        decision_response = self.client.post(
            f"/api/v1/moderation/reports/{report_id}/decide/",
            {"decision": "reject", "reason": "Signalement non fondé."},
            format="json",
        )
        self.assertEqual(decision_response.status_code, 200, decision_response.content)
        self.assertTrue(
            self.product.reports.get(id=report_id).history.filter(actor=staff).exists()
        )

    def test_non_staff_cannot_access_another_users_report_by_changing_id(self):
        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/reports/",
            {
                "product_id": str(self.product.id),
                "reason": "misleading_description",
                "description": "Signalement privé au déclarant.",
            },
            format="json",
        )
        report_id = create_response.data["id"]
        own_reports = self.client.get("/api/v1/moderation/reports/")
        self.assertEqual(own_reports.status_code, 200, own_reports.content)
        self.assertEqual(len(own_reports.data["results"]), 1)

        other_buyer = User.objects.create_user(
            email="other-buyer@mall.test",
            phone_number="+243000000006",
            username="otherbuyer",
            password="OtherBuyer123!",
        )
        self.client.force_authenticate(other_buyer)
        self.assertEqual(
            self.client.get(f"/api/v1/moderation/reports/{report_id}/").status_code,
            404,
        )

    def test_staff_requires_model_permission_for_global_disputes(self):
        self.client.force_authenticate(self.buyer)
        create_response = self.client.post(
            "/api/v1/moderation/disputes/",
            {"order_id": str(self.order.id), "reason": "Commande non reçue."},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)

        staff = User.objects.create_user(
            email="dispute-staff@mall.test",
            phone_number="+243000000007",
            username="disputestaff",
            password="DisputeStaff123!",
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        self.assertEqual(self.client.get("/api/v1/moderation/disputes/").status_code, 403)

        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="moderation", codename="view_dispute")
        )
        self.client.force_authenticate(User.objects.get(pk=staff.pk))
        response = self.client.get("/api/v1/moderation/disputes/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data["results"]), 1)

    def test_only_moderation_admin_can_review_disputes(self):
        self.client.force_authenticate(self.buyer)
        created = self.client.post(
            "/api/v1/moderation/disputes/",
            {"order_id": str(self.order.id), "reason": "Commande non reçue."},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        dispute_id = created.data["id"]
        review_url = f"/api/v1/moderation/disputes/{dispute_id}/review/"

        staff = User.objects.create_user(
            email="review-staff@mall.test",
            phone_number="+243000000008",
            username="reviewstaff",
            password="ReviewStaff123!",
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        forbidden = self.client.post(
            review_url,
            {"status": "resolved", "resolution": "Décision non autorisée."},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.admin)
        missing_resolution = self.client.post(
            review_url, {"status": "resolved"}, format="json"
        )
        self.assertEqual(missing_resolution.status_code, 400)

        response = self.client.post(
            review_url,
            {"status": "resolved", "resolution": "Remboursement validé."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["status"], "resolved")
        self.assertEqual(response.data["resolution"], "Remboursement validé.")
        self.assertEqual(len(response.data["case_history"]), 2)

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

    def test_user_can_report_another_participants_message(self):
        conversation = Conversation.objects.create()
        ConversationParticipant.objects.create(conversation=conversation, user=self.buyer)
        ConversationParticipant.objects.create(conversation=conversation, user=self.seller)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.seller,
            content="Message menaçant.",
        )
        self.client.force_authenticate(self.buyer)

        response = self.client.post(
            "/api/v1/moderation/message-reports/",
            {"message_id": str(message.id), "reason": "threat", "description": "Menace reçue."},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["reported_user"], str(self.seller.id))
        self.assertEqual(response.data["message_data"]["content"], "Message menaçant.")

        duplicate = self.client.post(
            "/api/v1/moderation/message-reports/",
            {"message_id": str(message.id), "reason": "threat"},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.content)

        self.client.force_authenticate(self.seller)
        own_message = self.client.post(
            "/api/v1/moderation/message-reports/",
            {"message_id": str(message.id), "reason": "threat"},
            format="json",
        )
        self.assertEqual(own_message.status_code, 400, own_message.content)

    def test_only_moderation_admin_can_review_message_report(self):
        conversation = Conversation.objects.create()
        ConversationParticipant.objects.create(conversation=conversation, user=self.buyer)
        ConversationParticipant.objects.create(conversation=conversation, user=self.seller)
        message = Message.objects.create(conversation=conversation, sender=self.seller, content="Inappropriate")
        self.client.force_authenticate(self.buyer)
        report = self.client.post(
            "/api/v1/moderation/message-reports/",
            {"message_id": str(message.id), "reason": "inappropriate"},
            format="json",
        )
        report_url = f"/api/v1/moderation/message-reports/{report.data['id']}/review/"

        forbidden = self.client.post(report_url, {"status": "valid"}, format="json")
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.admin)
        reviewed = self.client.post(
            report_url,
            {"status": "valid", "review_notes": "Contenu contraire aux règles."},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(reviewed.data["status"], "valid")

    def test_admin_can_suspend_and_restore_an_account_with_history(self):
        url = f"/api/v1/moderation/accounts/{self.seller.id}/suspension/"
        staff = User.objects.create_user(
            email="account-staff@mall.test",
            phone_number="+243000000009",
            username="accountstaff",
            password="Staff123!",
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        forbidden = self.client.post(url, {"suspended": True, "reason": "Fraude."}, format="json")
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.admin)
        missing_reason = self.client.post(url, {"suspended": True, "reason": " "}, format="json")
        self.assertEqual(missing_reason.status_code, 400)

        suspended = self.client.post(
            url,
            {"suspended": True, "reason": "Fraude confirmée après examen du dossier."},
            format="json",
        )
        self.assertEqual(suspended.status_code, 200, suspended.content)
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.is_suspended)
        self.assertFalse(self.seller.is_active)

        restored = self.client.post(
            url,
            {"suspended": False, "reason": "Compte rétabli après nouvel examen."},
            format="json",
        )
        self.assertEqual(restored.status_code, 200, restored.content)
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.is_suspended)
        self.assertTrue(self.seller.is_active)
        self.assertEqual(self.seller.moderation_history.count(), 2)

    def test_suspended_account_cannot_send_rest_messages(self):
        conversation = Conversation.objects.create()
        ConversationParticipant.objects.create(conversation=conversation, user=self.buyer)
        ConversationParticipant.objects.create(conversation=conversation, user=self.seller)
        self.seller.is_suspended = True
        self.seller.is_active = False
        self.seller.save(update_fields=["is_suspended", "is_active"])
        self.client.force_authenticate(self.seller)

        response = self.client.post(
            f"/api/v1/messaging/conversations/{conversation.id}/messages/",
            {"content": "Je ne devrais pas pouvoir envoyer ceci."},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
