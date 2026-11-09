from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.exceptions import ValidationError

from .models import Category, Product, ProductActivity, ProductIdentity, SellerFavorite, StockMovement
from .serializers import ProductCreateUpdateSerializer


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

    def test_seller_phone_requires_explicit_consent_and_authenticated_viewer(self):
        product = self.create_product(Product.Status.PUBLISHED)
        detail_url = reverse("catalog:product-detail", kwargs={"pk": product.id})

        anonymous_response = self.client.get(detail_url)
        self.assertIsNone(anonymous_response.data["seller_phone_number"])

        self.client.force_authenticate(self.other_user)
        authenticated_response = self.client.get(detail_url)
        self.assertIsNone(authenticated_response.data["seller_phone_number"])

        self.seller.show_phone_on_listings = True
        self.seller.save(update_fields=["show_phone_on_listings"])
        consented_response = self.client.get(detail_url)
        self.assertEqual(consented_response.data["seller_phone_number"], self.seller.phone_number)

        self.client.force_authenticate(user=None)
        anonymous_consented_response = self.client.get(detail_url)
        self.assertIsNone(anonymous_consented_response.data["seller_phone_number"])

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

    def test_views_count_ordering_is_supported(self):
        most_viewed = self.create_product(self.individual, title="Populaire", views_count=12)
        least_viewed = self.create_product(self.professional, title="Nouveau", views_count=2)

        response = self.client.get(self.url, {"ordering": "-views_count"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(most_viewed.pk), str(least_viewed.pk)],
        )


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


class ProductStockMovementTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.seller = User.objects.create_user(
            email="stock-seller@example.com",
            phone_number="+243900000091",
            username="stock-seller",
            password="password123",
        )
        self.category = Category.objects.create(name="Stock test")

    def save_product(self, data, instance=None):
        if instance and "stock_quantity" in data and "expected_stock_quantity" not in data:
            data = {**data, "expected_stock_quantity": instance.stock_quantity}
        serializer = ProductCreateUpdateSerializer(
            instance,
            data=data,
            partial=instance is not None,
            context={"request": type("Request", (), {"user": self.seller})()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_opening_adjustment_and_restock_are_recorded(self):
        product = self.save_product({
            "title": "Article de stock",
            "description": "Description",
            "category": str(self.category.pk),
            "price": "20.00",
            "currency": "USD",
            "condition": "bon_etat",
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 2,
            "status": Product.Status.PUBLISHED,
            "images": [],
        })
        self.assertEqual(
            StockMovement.objects.get(product=product).quantity_delta, 2
        )

        product = self.save_product({"stock_quantity": 0}, instance=product)
        self.assertEqual(product.status, Product.Status.SOLD)
        product = self.save_product({"stock_quantity": 3}, instance=product)
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertEqual(
            list(
                StockMovement.objects.filter(product=product)
                .order_by("created_at")
                .values_list("quantity_delta", flat=True)
            ),
            [2, -2, 3],
        )

    def test_stale_stock_edit_cannot_overwrite_a_concurrent_sale(self):
        product = self.save_product({
            "title": "Article concurrent",
            "description": "Description",
            "category": str(self.category.pk),
            "price": "20.00",
            "currency": "USD",
            "condition": "bon_etat",
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 4,
            "status": Product.Status.PUBLISHED,
            "images": [],
        })
        Product.objects.filter(pk=product.pk).update(stock_quantity=3)

        serializer = ProductCreateUpdateSerializer(
            product,
            data={"stock_quantity": 5, "expected_stock_quantity": 4},
            partial=True,
            context={"request": type("Request", (), {"user": self.seller})()},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError):
            serializer.save()

        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 3)

    def test_stock_quantity_is_in_seller_product_list(self):
        product = self.save_product({
            "title": "Article visible",
            "description": "Description",
            "category": str(self.category.pk),
            "price": "20.00",
            "currency": "USD",
            "condition": "bon_etat",
            "city": "Kinshasa",
            "country": "RDC",
            "stock_quantity": 7,
            "status": Product.Status.PUBLISHED,
            "images": [],
        })
        self.client.force_authenticate(self.seller)

        response = self.client.get(reverse("catalog:product-mine"))

        self.assertEqual(response.status_code, 200)
        result = next(item for item in response.data["results"] if item["id"] == str(product.pk))
        self.assertEqual(result["stock_quantity"], 7)


class ProductActivityTests(APITestCase):
    def test_product_view_is_unique_per_visitor(self):
        User = get_user_model()
        seller = User.objects.create_user(
            email="activity-seller@example.com",
            phone_number="+243900000099",
            username="activity-seller",
            password="password123",
        )
        category = Category.objects.create(name="Activity test")
        product = Product.objects.create(
            seller=seller,
            category=category,
            title="Article consulté",
            description="Test",
            price="10.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            stock_quantity=1,
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
        )
        visitor_id = "e220b04a-7fd2-4c12-a7be-f301472a9182"
        url = f"/api/v1/catalog/products/{product.pk}/track_activity/"

        first = self.client.post(url, {
            "activity_type": "view",
            "visitor_id": visitor_id,
            "event_id": "4e2eb623-f19d-4c13-ab24-11baf47cd6ee",
        }, format="json")
        second = self.client.post(url, {
            "activity_type": "view",
            "visitor_id": visitor_id,
            "event_id": "f33bb36e-8ee8-48df-b85b-c9806f12f842",
        }, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["recorded"])
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data["recorded"])
        product.refresh_from_db()
        self.assertEqual(product.views_count, 1)
        self.assertEqual(ProductActivity.objects.filter(product=product).count(), 1)
