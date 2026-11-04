from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Category, Product, ProductIdentity, SellerFavorite


class ProductVisibilityTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.seller = User.objects.create_user(
            email="seller@example.com",
            phone_number="+243900000001",
            username="seller",
            password="password123",
        )
        self.other_user = User.objects.create_user(
            email="buyer@example.com",
            phone_number="+243900000002",
            username="buyer",
            password="password123",
        )
        self.category = Category.objects.create(name="Téléphones")
        self.url = reverse("catalog:product-list")

    def product_payload(self, status):
        return {
            "title": f"Annonce {status}",
            "description": "Une annonce de test",
            "category": str(self.category.id),
            "price": "100.00",
            "currency": "USD",
            "condition": "bon_etat",
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 1,
            "shipping_cost": "0.00",
            "status": status,
            "images": [],
        }

    def create_product(self, status):
        self.client.force_authenticate(self.seller)
        response = self.client.post(self.url, self.product_payload(status), format="json")
        self.assertEqual(response.status_code, 201)
        return Product.objects.get(pk=response.data["id"])

    def test_published_product_is_visible_to_other_users(self):
        product = self.create_product(Product.Status.PUBLISHED)

        self.assertEqual(product.moderation_status, Product.ModerationStatus.APPROVED)
        self.client.force_authenticate(self.other_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(product.id))

    def test_draft_is_private_but_archived_product_is_public(self):
        draft = self.create_product(Product.Status.DRAFT)
        archived = self.create_product(Product.Status.ARCHIVED)

        self.client.force_authenticate(self.other_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(archived.id))
        self.client.force_authenticate(self.seller)
        response = self.client.get(self.url)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(draft.id), str(archived.id)})

        self.assertFalse(archived.is_available)

    def test_republishing_an_archived_product_approves_it(self):
        product = self.create_product(Product.Status.ARCHIVED)
        self.client.force_authenticate(self.seller)

        response = self.client.patch(
            reverse("catalog:product-detail", kwargs={"pk": product.id}),
            {"status": Product.Status.PUBLISHED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertEqual(product.moderation_status, Product.ModerationStatus.APPROVED)

    def test_seller_phone_is_returned_only_to_authenticated_product_viewers(self):
        product = self.create_product(Product.Status.PUBLISHED)
        detail_url = reverse("catalog:product-detail", kwargs={"pk": product.id})

        anonymous_response = self.client.get(detail_url)
        self.assertIsNone(anonymous_response.data["seller_phone_number"])

        self.client.force_authenticate(self.other_user)
        authenticated_response = self.client.get(detail_url)
        self.assertEqual(authenticated_response.data["seller_phone_number"], self.seller.phone_number)

    def test_authenticated_user_cannot_update_another_sellers_product(self):
        product = self.create_product(Product.Status.PUBLISHED)
        self.client.force_authenticate(self.other_user)
        response = self.client.patch(
            reverse("catalog:product-detail", kwargs={"pk": product.id}),
            {"title": "Tentative de modification"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_cannot_create_product(self):
        response = self.client.post(self.url, self.product_payload(Product.Status.PUBLISHED), format="json")
        self.assertEqual(response.status_code, 401)


class ProductCatalogFilterTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.professional = User.objects.create_user(
            email="professional@example.com",
            phone_number="+243900000010",
            username="professional",
            password="password123",
            seller_type="professional",
        )
        self.individual = User.objects.create_user(
            email="individual@example.com",
            phone_number="+243900000011",
            username="individual",
            password="password123",
        )
        self.category = Category.objects.create(name="Téléphones")
        self.url = reverse("catalog:product-list")

    def create_product(self, seller, **overrides):
        values = {
            "seller": seller,
            "category": self.category,
            "title": "Samsung Galaxy",
            "description": "Téléphone Android en bon état",
            "price": "200.00",
            "currency": "USD",
            "condition": Product.Condition.BON_ETAT,
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 2,
            "status": Product.Status.PUBLISHED,
            "moderation_status": Product.ModerationStatus.APPROVED,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_combined_search_filters_and_ordering(self):
        expected = self.create_product(self.professional)
        self.create_product(self.individual, title="Samsung Galaxy ancien", price="350.00")
        self.create_product(self.individual, title="Autre téléphone", price="150.00")

        response = self.client.get(self.url, {
            "search": "  SAMSUNG  ",
            "category": str(self.category.pk),
            "price_min": "100",
            "price_max": "300",
            "currency": "USD",
            "condition": Product.Condition.BON_ETAT,
            "seller_type": "professional",
            "city": "kinshasa",
            "ordering": "price",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(expected.pk))

    def test_search_matches_category_name_case_insensitively(self):
        expected = self.create_product(self.individual, title="Mobile récent")

        response = self.client.get(self.url, {"search": "  TÉLÉPHONES  "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(expected.pk))

    def test_price_range_requires_currency_and_valid_bounds(self):
        missing_currency = self.client.get(self.url, {"price_min": "100"})
        reversed_range = self.client.get(self.url, {
            "price_min": "300", "price_max": "100", "currency": "USD",
        })

        self.assertEqual(missing_currency.status_code, 400)
        self.assertIn("currency", missing_currency.data)
        self.assertEqual(reversed_range.status_code, 400)
        self.assertIn("price_max", reversed_range.data)

    def test_availability_excludes_archived_services_and_empty_stock(self):
        available_product = self.create_product(self.individual)
        self.create_product(self.individual, title="Rupture", stock_quantity=0)
        self.create_product(self.individual, title="Archivé", status=Product.Status.ARCHIVED)
        self.create_product(self.individual, title="Service", item_type=Product.ItemType.SERVICE)

        response = self.client.get(self.url, {"available": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(available_product.pk))

    def test_unknown_ordering_is_rejected(self):
        response = self.client.get(self.url, {"ordering": "seller__email"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("ordering", response.data)


class SellerFavoriteTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(
            email="favorite-buyer@example.com",
            phone_number="+243900000003",
            username="favorite-buyer",
            password="password123",
        )
        self.seller = User.objects.create_user(
            email="favorite-seller@example.com",
            phone_number="+243900000004",
            username="favorite-seller",
            password="password123",
            first_name="Vendeur",
            city="Kinshasa",
        )
        self.url = reverse("catalog:seller-favorite-list")
        self.client.force_authenticate(self.buyer)

    def test_user_can_list_add_and_remove_favorite_sellers(self):
        response = self.client.post(self.url, {"seller": str(self.seller.pk)}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["seller_username"], self.seller.username)
        self.assertEqual(response.data["city"], self.seller.city)
        favorite_id = response.data["id"]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], favorite_id)

        response = self.client.delete(
            reverse("catalog:seller-favorite-detail", kwargs={"pk": favorite_id})
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SellerFavorite.objects.filter(user=self.buyer).exists())

    def test_user_cannot_favorite_themselves_or_duplicate_a_seller(self):
        self.assertEqual(
            self.client.post(self.url, {"seller": str(self.buyer.pk)}, format="json").status_code,
            400,
        )
        self.client.post(self.url, {"seller": str(self.seller.pk)}, format="json")
        response = self.client.post(self.url, {"seller": str(self.seller.pk)}, format="json")

        self.assertEqual(response.status_code, 400)


class ProductComparisonTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.sellers = [
            User.objects.create_user(
                email=f"compare-{index}@example.com",
                phone_number=f"+2439000010{index}",
                username=f"compare-{index}",
                password="password123",
            )
            for index in range(4)
        ]
        self.category = Category.objects.create(name="Téléphones")
        self.identity = ProductIdentity.objects.create(
            category=self.category,
            name="Samsung Galaxy A15 128 Go",
            brand="Samsung",
            model_name="Galaxy A15",
            variant="128 Go",
        )
        self.url = reverse("catalog:product-list")

    def create_product(self, seller, **overrides):
        values = {
            "seller": seller,
            "category": self.category,
            "title": "Samsung Galaxy A15 128 Go",
            "description": "Téléphone de test",
            "price": "200.00",
            "currency": "USD",
            "condition": Product.Condition.BON_ETAT,
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 1,
            "status": Product.Status.PUBLISHED,
            "moderation_status": Product.ModerationStatus.APPROVED,
            "comparison_identity": self.identity,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_exact_offers_use_identity_and_exclude_unavailable_listings(self):
        reference = self.create_product(self.sellers[0], price="300.00")
        cheapest = self.create_product(self.sellers[1], price="180.00")
        self.create_product(self.sellers[2], price="150.00", currency="CDF")
        self.create_product(self.sellers[2], price="5.00", is_suspended=True)
        self.create_product(self.sellers[3], price="10.00", stock_quantity=0)

        response = self.client.get(
            reverse("catalog:product-comparisons", kwargs={"pk": reference.pk})
        )

        self.assertEqual(response.status_code, 200)
        exact = response.data["exact"]
        self.assertEqual(exact["offer_count"], 2)
        self.assertEqual(exact["seller_count"], 2)
        self.assertEqual(exact["lowest_price"], "180.00")
        self.assertEqual(exact["currency"], "USD")
        self.assertEqual(
            {offer["id"] for offer in exact["results"]},
            {str(reference.pk), str(cheapest.pk)},
        )
        self.assertFalse(exact["results"][0]["shipping_cost_known"])

    def test_similar_titles_are_not_reported_as_exact_matches(self):
        reference = self.create_product(
            self.sellers[0],
            title="Samsung Galaxy S21 128GB",
            comparison_identity=None,
        )
        self.create_product(
            self.sellers[1],
            title="Samsung Galaxy S21 Ultra 128GB",
            comparison_identity=None,
        )

        response = self.client.get(
            reverse("catalog:product-comparisons", kwargs={"pk": reference.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["exact"]["identity"])
        self.assertEqual(response.data["exact"]["offer_count"], 0)
        self.assertEqual(len(response.data["similar"]), 1)

    def test_different_variants_have_different_identity_keys(self):
        other_variant = ProductIdentity.objects.create(
            category=self.category,
            name="Samsung Galaxy A15 256 Go",
            brand="Samsung",
            model_name="Galaxy A15",
            variant="256 Go",
        )
        reference = self.create_product(self.sellers[0])
        alternative = self.create_product(
            self.sellers[1],
            comparison_identity=other_variant,
            title="Samsung Galaxy A15 256 Go",
        )

        response = self.client.get(
            reverse("catalog:product-comparisons", kwargs={"pk": reference.pk})
        )

        self.assertEqual(response.data["exact"]["offer_count"], 1)
        self.assertNotIn(
            str(alternative.pk),
            {offer["id"] for offer in response.data["exact"]["results"]},
        )

    def test_catalog_lists_only_same_currency_exact_group_summary(self):
        first = self.create_product(self.sellers[0], price="250.00")
        self.create_product(self.sellers[1], price="190.00")
        self.create_product(self.sellers[2], price="100.00", currency="CDF")

        response = self.client.get(self.url, {"search": "Samsung Galaxy A15"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        result = next(item for item in response.data["results"] if item["id"] == str(first.pk))
        self.assertEqual(result["comparison_offer_count"], 2)
        self.assertEqual(result["comparison_seller_count"], 2)
        self.assertEqual(result["comparison_lowest_price"], "190.00")
