from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from orders.models import Order
from orders.serializers import OrderCancelSerializer, OrderCreateSerializer
from negotiations.models import Negotiation

from .models import LoyaltyProgram, LoyaltyTransaction, Promotion
from .services import award_order_points, get_points_balance


class PromotionCheckoutTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="promotion-buyer@mall.test",
            phone_number="+243000000041",
            username="promotionbuyer",
            password="Buyer123!",
        )
        self.seller = User.objects.create_user(
            email="promotion-seller@mall.test",
            phone_number="+243000000042",
            username="promotionseller",
            password="Seller123!",
        )
        category = Category.objects.create(name="Promotion")
        self.product = Product.objects.create(
            seller=self.seller,
            category=category,
            title="Article en promotion",
            description="Test",
            price="100.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            shipping_cost="5.00",
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        self.program = LoyaltyProgram.objects.get(pk=1)

    def create_order(self, points=0):
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse privée de test",
                "points_to_redeem": points,
                "items": [{
                    "product_id": str(self.product.pk),
                    "quantity": 1,
                    "unit_price": "100.00",
                    "shipping_cost": "5.00",
                }],
            },
            context={"request": type("Request", (), {"user": self.buyer})()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_seller_promotion_sets_discounted_price_and_free_shipping(self):
        promotion = Promotion.objects.create(
            seller=self.seller,
            name="Lancement",
            discount_type=Promotion.DiscountType.PERCENTAGE,
            value="10.00",
            free_shipping=True,
        )
        promotion.products.add(self.product)

        group = self.create_order()
        item = group.items.get()

        self.assertEqual(item.original_unit_price, Decimal("100.00"))
        self.assertEqual(item.unit_price, Decimal("90.00"))
        self.assertEqual(item.promotion_discount, Decimal("10.00"))
        self.assertEqual(item.promotion_name, "Lancement")
        self.assertEqual(item.original_shipping_cost, Decimal("5.00"))
        self.assertEqual(item.shipping_cost, Decimal("0.00"))
        self.assertEqual(group.total_amount, Decimal("90.00"))

    def test_negotiated_price_is_used_and_not_stacked_with_a_promotion(self):
        promotion = Promotion.objects.create(
            seller=self.seller,
            name="Promotion non cumulable",
            discount_type=Promotion.DiscountType.PERCENTAGE,
            value="20.00",
        )
        promotion.products.add(self.product)
        reserved_until = timezone.now() + timedelta(minutes=10)
        negotiation = Negotiation.objects.create(
            product=self.product,
            buyer=self.buyer,
            seller=self.seller,
            status=Negotiation.Status.ACCEPTED,
            accepted_price=Decimal("80.00"),
            expires_at=reserved_until,
            reserved_until=reserved_until,
        )
        serializer = OrderCreateSerializer(
            data={
                "shipping_address": "Adresse privée de test",
                "items": [{
                    "product_id": str(self.product.pk),
                    "negotiation_id": str(negotiation.pk),
                    "quantity": 1,
                    "unit_price": "80.00",
                    "shipping_cost": "5.00",
                }],
            },
            context={"request": type("Request", (), {"user": self.buyer})()},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        group = serializer.save()
        item = group.items.get()
        negotiation.refresh_from_db()

        self.assertEqual(item.unit_price, Decimal("80.00"))
        self.assertEqual(item.promotion_discount, Decimal("0.00"))
        self.assertEqual(item.promotion_name, "Prix négocié")
        self.assertEqual(group.total_amount, Decimal("85.00"))
        self.assertEqual(negotiation.status, Negotiation.Status.COMPLETED)

    def test_points_are_spent_and_restored_when_order_is_cancelled(self):
        self.program.redemption_value_per_point = Decimal("0.01")
        self.program.max_redemption_percent = Decimal("100.00")
        self.program.save()
        LoyaltyTransaction.objects.create(
            user=self.buyer,
            kind=LoyaltyTransaction.Kind.EARNED,
            points_delta=200,
        )

        group = self.create_order(points=100)
        item = group.items.get()
        self.assertEqual(group.loyalty_points_redeemed, 100)
        self.assertEqual(group.total_amount, Decimal("104.00"))
        self.assertEqual(item.loyalty_discount, Decimal("1.00"))
        self.assertEqual(item.loyalty_points_redeemed, 100)
        self.assertEqual(get_points_balance(self.buyer), 100)

        order = group.orders.get()
        cancel = OrderCancelSerializer(data={}, context={"order": order})
        self.assertTrue(cancel.is_valid(), cancel.errors)
        cancel.save()

        self.assertEqual(get_points_balance(self.buyer), 200)
        self.assertEqual(
            LoyaltyTransaction.objects.filter(
                order=order, kind=LoyaltyTransaction.Kind.REFUNDED
            ).get().points_delta,
            100,
        )

    def test_points_are_awarded_once_only_after_delivery(self):
        self.program.points_per_currency_unit = Decimal("1.00")
        self.program.save()
        order = self.create_order().orders.get()
        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])

        self.assertEqual(award_order_points(order), 105)
        self.assertEqual(award_order_points(order), 0)
        self.assertEqual(get_points_balance(self.buyer), 105)

    def test_sellers_cannot_create_promotions_for_another_sellers_product(self):
        other_seller = User.objects.create_user(
            email="other-promotion-seller@mall.test",
            phone_number="+243000000043",
            username="otherpromoseller",
            password="Seller123!",
        )
        other_product = Product.objects.create(
            seller=other_seller,
            category=self.product.category,
            title="Annonce étrangère",
            description="Test",
            price="25.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
        )
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(
            "/api/v1/promotions/mine/",
            {
                "name": "Offre non autorisée",
                "products": [str(other_product.pk)],
                "discount_type": "percentage",
                "value": "10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Promotion.objects.exists())