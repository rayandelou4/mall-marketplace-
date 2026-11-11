from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from orders.models import Order, OrderItem
from payments.models import Commission


class GlobalStatsAPITests(TestCase):
	url = "/api/v1/analytics/stats/"

	def setUp(self):
		self.client = APIClient()
		self.buyer = User.objects.create_user(
			email="buyer@mall.test",
			phone_number="+243000000011",
			username="buyer",
			password="Buyer123!",
		)
		self.individual = User.objects.create_user(
			email="individual@mall.test",
			phone_number="+243000000012",
			username="individual",
			password="Individual123!",
			seller_type=User.SellerType.INDIVIDUAL,
		)
		self.professional = User.objects.create_user(
			email="professional@mall.test",
			phone_number="+243000000013",
			username="professional",
			password="Professional123!",
			seller_type=User.SellerType.PROFESSIONAL,
		)
		self.staff = User.objects.create_user(
			email="staff@mall.test",
			phone_number="+243000000014",
			username="staff",
			password="Staff123!",
			is_staff=True,
		)

	def test_anonymous_and_marketplace_accounts_cannot_read_global_stats(self):
		self.assertEqual(self.client.get(self.url).status_code, 401)

		for user in (self.buyer, self.individual, self.professional):
			self.client.force_authenticate(user)
			response = self.client.get(self.url)
			self.assertEqual(response.status_code, 403, response.content)

	def test_staff_can_read_real_stats_without_shared_cache(self):
		self.client.force_authenticate(self.staff)
		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200, response.content)
		self.assertEqual(response.data["users"]["total"], 4)
		self.assertEqual(response.data["sellers"]["total"], 0)
		self.assertIn("active_listings", response.data["products"])
		self.assertIn("pending", response.data["verification"])
		self.assertIn("no-store", response.headers["Cache-Control"])

	def test_seller_totals_count_only_accounts_with_available_listings(self):
		category = Category.objects.create(name="Annonces actives")
		Product.objects.create(
			seller=self.individual,
			category=category,
			title="Produit disponible",
			description="Test",
			price="20.00",
			currency="USD",
			city="Kinshasa",
			country="RDC",
			stock_quantity=1,
			status=Product.Status.PUBLISHED,
			moderation_status=Product.ModerationStatus.APPROVED,
		)
		Product.objects.create(
			seller=self.professional,
			category=category,
			title="Service disponible",
			description="Test",
			price="20.00",
			currency="USD",
			city="Kinshasa",
			country="RDC",
			stock_quantity=0,
			item_type=Product.ItemType.SERVICE,
			status=Product.Status.PUBLISHED,
			moderation_status=Product.ModerationStatus.APPROVED,
		)
		Product.objects.create(
			seller=self.buyer,
			category=category,
			title="Produit épuisé",
			description="Test",
			price="20.00",
			currency="USD",
			city="Kinshasa",
			country="RDC",
			stock_quantity=0,
			status=Product.Status.PUBLISHED,
			moderation_status=Product.ModerationStatus.APPROVED,
		)
		self.client.force_authenticate(self.staff)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200, response.content)
		self.assertEqual(response.data["sellers"]["total"], 2)
		self.assertEqual(response.data["sellers"]["individual"], 1)
		self.assertEqual(response.data["sellers"]["professional"], 1)

	def test_admin_revenue_uses_delivered_orders_and_recorded_commissions(self):
		delivered = Order.objects.create(
			buyer=self.buyer,
			status=Order.Status.DELIVERED,
			total_amount="60.00",
			currency="USD",
		)
		Order.objects.create(
			buyer=self.buyer,
			status=Order.Status.PENDING,
			total_amount="900.00",
			currency="USD",
		)
		Commission.objects.create(order=delivered, rate="5.00", amount="3.00")
		self.client.force_authenticate(self.staff)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200, response.content)
		self.assertEqual(response.data["revenue"]["gmv_by_currency"]["USD"], 60)
		self.assertEqual(
			response.data["revenue"]["commissions_by_currency"]["USD"], 3
		)


class SellerStatsAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.buyer = User.objects.create_user(
			email="seller-stats-buyer@mall.test",
			phone_number="+243000000021",
			username="sellerstatsbuyer",
			password="Buyer123!",
		)
		self.seller = User.objects.create_user(
			email="seller-stats@mall.test",
			phone_number="+243000000022",
			username="sellerstats",
			password="Seller123!",
		)
		self.other_seller = User.objects.create_user(
			email="other-seller-stats@mall.test",
			phone_number="+243000000023",
			username="othersellerstats",
			password="Seller123!",
		)
		category = Category.objects.create(name="Seller stats")
		self.product = Product.objects.create(
			seller=self.seller,
			category=category,
			title="Produit du vendeur",
			description="Test",
			price="30.00",
			currency="USD",
			city="Kinshasa",
			country="RDC",
			views_count=12,
			favorites_count=3,
		)
		self.other_product = Product.objects.create(
			seller=self.other_seller,
			category=category,
			title="Produit privé",
			description="Test",
			price="200.00",
			currency="USD",
			city="Kinshasa",
			country="RDC",
		)

	def add_order_item(self, buyer, seller, product, status, quantity, loyalty_discount="0.00"):
		order = Order.objects.create(
			buyer=buyer,
			status=status,
			total_amount=str(product.price * quantity),
			currency=product.currency,
		)
		OrderItem.objects.create(
			order=order,
			product=product,
			seller=seller,
			product_title=product.title,
			quantity=quantity,
			unit_price=product.price,
			loyalty_discount=loyalty_discount,
		)
		return order

	def test_seller_stats_are_scoped_and_exclude_unfinished_sales(self):
		self.add_order_item(
			self.buyer, self.seller, self.product, Order.Status.DELIVERED, 2, "5.00"
		)
		self.add_order_item(
			self.buyer, self.seller, self.product, Order.Status.PENDING, 4
		)
		self.add_order_item(
			self.buyer, self.other_seller, self.other_product, Order.Status.DELIVERED, 8
		)
		self.client.force_authenticate(self.seller)

		response = self.client.get("/api/v1/analytics/seller/?period=daily")

		self.assertEqual(response.status_code, 200, response.content)
		self.assertEqual(response.data["products"]["total"], 1)
		self.assertEqual(response.data["sales"]["units"], 2)
		self.assertEqual(response.data["sales"]["orders"], 1)
		self.assertEqual(response.data["sales"]["orders_received"], 2)
		self.assertEqual(response.data["sales"]["orders_pending"], 1)
		self.assertEqual(response.data["transactions"]["successful"], 1)
		self.assertEqual(response.data["sales"]["revenue_by_currency"][0]["amount"], 55)
		self.assertEqual(response.data["sales"]["top_products"][0]["product_title"], self.product.title)
		self.assertEqual(response.data["sales"]["series"][0]["units"], 2)

	def test_period_sales_exclude_delivered_orders_outside_selected_window(self):
		self.add_order_item(
			self.buyer, self.seller, self.product, Order.Status.DELIVERED, 2
		)
		old_order = self.add_order_item(
			self.buyer, self.seller, self.product, Order.Status.DELIVERED, 3
		)
		Order.objects.filter(pk=old_order.pk).update(
			created_at=timezone.now() - timedelta(days=40)
		)
		self.client.force_authenticate(self.seller)

		response = self.client.get("/api/v1/analytics/seller/?period=daily")

		self.assertEqual(response.status_code, 200, response.content)
		self.assertEqual(response.data["sales"]["units"], 5)
		self.assertEqual(response.data["period_sales"]["units"], 2)
		self.assertEqual(response.data["period_sales"]["products_sold"], 1)
		self.assertEqual(response.data["period_sales"]["orders"], 1)
		self.assertEqual(response.data["period_sales"]["orders_received"], 1)
		self.assertEqual(response.data["period_sales"]["revenue_by_currency"][0]["amount"], 60)
