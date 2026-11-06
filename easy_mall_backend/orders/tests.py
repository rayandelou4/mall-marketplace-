from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from payments.models import Payment, PaymentProvider
from payments.serializers import PaymentInitiateSerializer
from notifications.models import Notification
from localization.models import Country, PrivateAddress

from .models import Order
from .serializers import (
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
)


class OrderCheckoutTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            phone_number="+10000000001",
            username="buyer",
            password="test-password",
        )
        self.seller = User.objects.create_user(
            email="seller@example.com",
            phone_number="+10000000002",
            username="seller",
            password="test-password",
        )
        self.category = Category.objects.create(name="Test", slug="test")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Produit test",
            description="Test",
            price="10.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            stock_quantity=5,
            shipping_cost="3.00",
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        self.request = SimpleNamespace(user=self.buyer)

    def create_order(self, items):
        serializer = OrderCreateSerializer(
            data={"shipping_address": "Adresse test", "items": items},
            context={"request": self.request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_order_total_includes_shipping_once_per_product_line(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 2}])

        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.total_amount, 23)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

    def test_pickup_checkout_does_not_require_address_or_charge_shipping(self):
        self.product.sale_method = Product.SaleMethod.PICKUP
        self.product.save(update_fields=["sale_method"])
        serializer = OrderCreateSerializer(
            data={"items": [{"product_id": str(self.product.pk), "quantity": 1}]},
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        self.assertEqual(order.shipping_address, "")
        self.assertEqual(order.total_amount, 10)
        self.assertEqual(order.items.get().sale_method, Product.SaleMethod.PICKUP)
        self.assertEqual(order.items.get().shipping_cost, 0)

    def test_mixed_delivery_and_pickup_total_only_charges_delivery(self):
        self.product.sale_method = Product.SaleMethod.PICKUP
        self.product.save(update_fields=["sale_method"])
        delivery_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Produit à livrer",
            description="Test",
            price="20.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            stock_quantity=2,
            shipping_cost="6.00",
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse test",
                "items": [
                    {"product_id": str(self.product.pk), "quantity": 1},
                    {"product_id": str(delivery_product.pk), "quantity": 1},
                ],
            },
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        self.assertEqual(order.total_amount, 36)
        self.assertEqual(
            order.items.get(product=self.product).shipping_cost, 0
        )
        self.assertEqual(
            order.items.get(product=delivery_product).shipping_cost, 6
        )

    def test_checkout_uses_only_buyers_saved_address_and_keeps_snapshot(self):
        country = Country.objects.create(code="CD", name="RDC")
        address = PrivateAddress.objects.create(
            user=self.buyer,
            country=country,
            street_address="Avenue de la Paix 12",
            landmark="Près du marché",
        )
        serializer = OrderCreateSerializer(
            data={
                "private_address_id": str(address.pk),
                "items": [{"product_id": str(self.product.pk), "quantity": 1}],
            },
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        snapshot = order.shipping_address
        self.assertEqual(order.shipping_address_record_id, address.pk)
        self.assertIn("Avenue de la Paix 12", snapshot)

        address.street_address = "Nouvelle adresse"
        address.save(update_fields=["street_address"])
        order.refresh_from_db()
        response_data = OrderDetailSerializer(order).data
        self.assertEqual(order.shipping_address, snapshot)
        self.assertNotIn("shipping_address_record", response_data)
        self.assertEqual(response_data["shipping_address"], snapshot)
        seller_sale_data = OrderItemSerializer(order.items.get()).data
        self.assertEqual(seller_sale_data["shipping_address"], snapshot)

    def test_checkout_rejects_another_users_saved_address(self):
        country = Country.objects.create(code="CD", name="RDC")
        address = PrivateAddress.objects.create(
            user=self.seller,
            country=country,
            street_address="Adresse du vendeur",
        )
        serializer = OrderCreateSerializer(
            data={
                "private_address_id": str(address.pk),
                "items": [{"product_id": str(self.product.pk), "quantity": 1}],
            },
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("private_address_id", serializer.errors)

    def test_order_creation_notifies_each_seller_once(self):
        second_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Autre produit",
            description="Test",
            price="5.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            stock_quantity=2,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )

        self.create_order(
            [
                {"product_id": str(self.product.pk), "quantity": 1},
                {"product_id": str(second_product.pk), "quantity": 1},
            ]
        )

        notifications = Notification.objects.filter(
            user=self.seller,
            notification_type=Notification.NotificationType.NEW_SALE,
        )
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications.get().link_path, "/vendeur?section=sales")

    def test_cash_order_records_payment_method_and_waits_for_shipment(self):
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse test",
                "payment_method": Order.PaymentMethod.CASH,
                "items": [{"product_id": str(self.product.pk), "quantity": 1}],
            },
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CASH)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(order.items.get().is_shipped)
        provider = PaymentProvider.objects.create(code="card", provider_type="card")
        payment_serializer = PaymentInitiateSerializer(
            data={"order_id": str(order.pk), "provider_id": str(provider.pk)},
            context={"request": self.request},
        )
        self.assertFalse(payment_serializer.is_valid())

    def test_cash_confirmation_delivers_pending_order_once_and_notifies_each_seller(
        self,
    ):
        second_seller = User.objects.create_user(
            email="seller2@example.com",
            phone_number="+10000000003",
            username="seller2",
            password="test-password",
        )
        second_product = Product.objects.create(
            seller=second_seller,
            category=self.category,
            title="Deuxième produit test",
            description="Test",
            price="5.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            stock_quantity=2,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        order = self.create_order(
            [
                {"product_id": str(self.product.pk), "quantity": 1},
                {"product_id": str(second_product.pk), "quantity": 1},
            ]
        )
        self.assertEqual(order.payment_method, Order.PaymentMethod.CASH)
        client = APIClient()

        client.force_authenticate(user=self.seller)
        response = client.post(
            f"/api/v1/orders/orders/{order.pk}/confirm_receipt/", {}, format="json"
        )
        self.assertEqual(response.status_code, 404)

        client.force_authenticate(user=self.buyer)
        response = client.post(
            f"/api/v1/orders/orders/{order.pk}/confirm_receipt/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertFalse(Payment.objects.filter(order=order).exists())
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        second_seller.refresh_from_db()
        self.assertEqual(self.buyer.total_purchases, 1)
        self.assertEqual(self.seller.total_sales, 1)
        self.assertEqual(second_seller.total_sales, 1)
        self.assertEqual(
            Notification.objects.filter(
                user__in=[self.seller, second_seller],
                notification_type=Notification.NotificationType.DELIVERY,
            ).count(),
            2,
        )
        client.force_authenticate(user=self.seller)
        response = client.get("/api/v1/orders/my-sales/confirmed-count/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        client.force_authenticate(user=self.buyer)
        response = client.post(
            f"/api/v1/orders/orders/{order.pk}/confirm_receipt/", {}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        second_seller.refresh_from_db()
        self.assertEqual(self.buyer.total_purchases, 1)
        self.assertEqual(self.seller.total_sales, 1)
        self.assertEqual(second_seller.total_sales, 1)

    @override_settings(PAYMENTS_MODE="online")
    def test_online_mode_creates_mobile_money_order_and_keeps_release_flow(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 1}])
        self.assertEqual(order.payment_method, Order.PaymentMethod.MOBILE_MONEY)
        order.status = Order.Status.PAID
        order.save(update_fields=["status"])
        client = APIClient()
        client.force_authenticate(user=self.buyer)

        with patch("orders.views.release_order_payment") as release_payment:
            response = client.post(
                f"/api/v1/orders/orders/{order.pk}/confirm_receipt/", {}, format="json"
            )

        self.assertEqual(response.status_code, 200)
        release_payment.assert_called_once()

    def test_order_rejects_products_with_different_currencies(self):
        other_product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Produit CDF",
            description="Test",
            price="100.00",
            currency="CDF",
            city="Kinshasa",
            country="RDC",
            stock_quantity=2,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse test",
                "items": [
                    {"product_id": str(self.product.pk), "quantity": 1},
                    {"product_id": str(other_product.pk), "quantity": 1},
                ],
            },
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("devise", str(serializer.errors).lower())

    def test_order_rejects_stale_price_snapshot(self):
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse test",
                "items": [
                    {
                        "product_id": str(self.product.pk),
                        "quantity": 1,
                        "unit_price": "9.00",
                        "shipping_cost": "3.00",
                    }
                ],
            },
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("ont changé", str(serializer.errors))

    def test_duplicate_product_lines_are_aggregated_before_stock_validation(self):
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse test",
                "items": [
                    {"product_id": str(self.product.pk), "quantity": 3},
                    {"product_id": str(self.product.pk), "quantity": 3},
                ],
            },
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("Stock insuffisant", str(serializer.errors))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_cancelling_pending_order_restores_stock_and_fails_pending_payment(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 5}])
        order.payment_method = Order.PaymentMethod.MOBILE_MONEY
        order.save(update_fields=["payment_method"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertEqual(self.product.status, Product.Status.SOLD)
        provider = PaymentProvider.objects.create(code="card", provider_type="card")
        payment_serializer = PaymentInitiateSerializer(
            data={"order_id": str(order.pk), "provider_id": str(provider.pk)},
            context={"request": self.request},
        )
        self.assertTrue(payment_serializer.is_valid(), payment_serializer.errors)
        payment = payment_serializer.save()

        cancel_serializer = OrderCancelSerializer(data={}, context={"order": order})
        self.assertTrue(cancel_serializer.is_valid(), cancel_serializer.errors)
        cancelled_order = cancel_serializer.save()

        self.product.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(cancelled_order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(self.product.status, Product.Status.PUBLISHED)
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_paid_order_cannot_be_cancelled_without_refund_flow(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 1}])
        order.status = Order.Status.PAID
        order.save(update_fields=["status"])
        serializer = OrderCancelSerializer(data={}, context={"order": order})

        self.assertFalse(serializer.is_valid())

    def test_retrying_payment_for_same_order_reuses_pending_payment(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 1}])
        order.payment_method = Order.PaymentMethod.MOBILE_MONEY
        order.save(update_fields=["payment_method"])
        provider = PaymentProvider.objects.create(code="card", provider_type="card")
        payload = {"order_id": str(order.pk), "provider_id": str(provider.pk)}

        first_serializer = PaymentInitiateSerializer(
            data=payload, context={"request": self.request}
        )
        self.assertTrue(first_serializer.is_valid(), first_serializer.errors)
        first_payment = first_serializer.save()
        retry_serializer = PaymentInitiateSerializer(
            data=payload, context={"request": self.request}
        )
        self.assertTrue(retry_serializer.is_valid(), retry_serializer.errors)
        retry_payment = retry_serializer.save()

        self.assertEqual(first_payment.pk, retry_payment.pk)
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)

    def test_buyer_can_hide_only_delivered_or_cancelled_orders(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 1}])
        client = APIClient()
        client.force_authenticate(user=self.buyer)
        order_url = f"/api/v1/orders/orders/{order.pk}/"

        response = client.delete(order_url)
        self.assertEqual(response.status_code, 400)

        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])
        response = client.delete(order_url)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertEqual(client.get("/api/v1/orders/orders/").data["count"], 0)

    def test_seller_can_hide_only_delivered_or_cancelled_sales(self):
        order = self.create_order([{"product_id": str(self.product.pk), "quantity": 1}])
        item = order.items.get()
        client = APIClient()
        client.force_authenticate(user=self.seller)
        item_url = f"/api/v1/orders/my-sales/{item.pk}/"

        response = client.delete(item_url)
        self.assertEqual(response.status_code, 400)

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        response = client.delete(item_url)
        self.assertEqual(response.status_code, 204)
        item.refresh_from_db()
        self.assertTrue(item.hidden_by_seller)
        self.assertEqual(client.get("/api/v1/orders/my-sales/").data["count"], 0)
