from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User


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
		self.assertIn("active_listings", response.data["products"])
		self.assertIn("pending", response.data["verification"])
		self.assertIn("no-store", response.headers["Cache-Control"])
