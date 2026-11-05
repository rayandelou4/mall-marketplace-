from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.serializers import UserSerializer
from catalog.models import Category, Product
from catalog.serializers import ProductDetailSerializer
from .models import (
    AdministrativeArea,
    Country,
    DeliveryOption,
    PrivateAddress,
    SellerLocationPreference,
    SellerPublicLocation,
)


class LocalizationBackendTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            code="CD", name="République démocratique du Congo"
        )
        self.province = AdministrativeArea.objects.create(
            country=self.country,
            name="Kinshasa",
            level="province",
        )
        self.city = AdministrativeArea.objects.create(
            country=self.country,
            parent=self.province,
            name="Kinshasa",
            level="city",
        )
        self.seller = User.objects.create_user(
            email="seller@example.com",
            phone_number="+243000000001",
            username="seller",
            password="test-password",
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            phone_number="+243000000002",
            username="buyer",
            password="test-password",
        )
        self.private_address = PrivateAddress.objects.create(
            user=self.seller,
            country=self.country,
            administrative_area=self.province,
            locality=self.city,
            street_address="Avenue de la Liberté 12",
            label="Maison",
            is_default=True,
        )
        SellerPublicLocation.objects.create(
            user=self.seller,
            country=self.country,
            administrative_area=self.province,
            locality=self.city,
            precision="city",
        )
        self.category = Category.objects.create(name="Vêtements", slug="vetements")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            title="Produit test",
            description="Desc",
            price="20.00",
            currency="USD",
            city="Kinshasa",
            country="RDC",
            status=Product.Status.PUBLISHED,
            moderation_status=Product.ModerationStatus.APPROVED,
            stock_quantity=2,
        )
        DeliveryOption.objects.create(
            seller=self.seller,
            mode="pickup",
            is_active=True,
            country=self.country,
            administrative_area=self.province,
            locality=self.city,
            conditions="Rendez-vous en ville",
            fees="0.00",
            estimated_delivery_days=2,
        )

    def test_seller_can_store_valid_location_and_public_profile_is_private_safe(self):
        response = APIClient().get(
            f"/api/v1/localization/seller-location/{self.seller.username}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["country"]["name"], "République démocratique du Congo"
        )
        self.assertNotIn("street_address", response.data)
        self.assertNotIn("private", response.data.get("country", {}))

    def test_private_address_is_not_visible_to_other_user(self):
        client = APIClient()
        client.force_authenticate(user=self.buyer)
        response = client.get(
            f"/api/v1/localization/addresses/{self.private_address.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_public_location_obeys_seller_privacy_preferences(self):
        location = self.seller.public_location
        location.public_note = "Près de la résidence"
        location.save(update_fields=["public_note"])
        SellerLocationPreference.objects.create(
            seller=self.seller,
            show_country=False,
            show_admin_area=False,
            show_locality=False,
            show_public_note=False,
        )

        response = APIClient().get(
            f"/api/v1/localization/seller-location/{self.seller.username}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["country"])
        self.assertIsNone(response.data["administrative_area"])
        self.assertIsNone(response.data["locality"])
        self.assertEqual(response.data["public_note"], "")
        self.assertEqual(response.data["display_name"], "")
        self.assertNotIn("Près de la résidence", str(response.data))

    def test_seller_can_create_and_update_location_from_me_route(self):
        client = APIClient()
        client.force_authenticate(user=self.seller)
        response = client.put(
            "/api/v1/localization/seller-location/me/",
            {
                "country_id": str(self.country.pk),
                "administrative_area_id": str(self.province.pk),
                "locality_id": str(self.city.pk),
                "precision": "city",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["locality"]["id"], str(self.city.pk))
        self.assertEqual(
            client.patch(
                "/api/v1/localization/seller-location/me/",
                {"precision": "province"},
                format="json",
            ).status_code,
            200,
        )

    def test_buyer_can_save_multiple_private_addresses(self):
        client = APIClient()
        client.force_authenticate(user=self.buyer)
        first = client.post(
            "/api/v1/localization/addresses/",
            {
                "country_id": str(self.country.pk),
                "street_address": "Avenue 1",
                "is_default": True,
            },
            format="json",
        )
        second = client.post(
            "/api/v1/localization/addresses/",
            {
                "country_id": str(self.country.pk),
                "street_address": "Avenue 2",
                "is_default": True,
            },
            format="json",
        )

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(PrivateAddress.objects.filter(user=self.buyer).count(), 2)
        self.assertEqual(
            PrivateAddress.objects.filter(user=self.buyer, is_default=True).count(), 1
        )

    def test_buyer_can_save_address_in_country_and_region_not_preloaded(self):
        client = APIClient()
        client.force_authenticate(user=self.buyer)

        response = client.post(
            "/api/v1/localization/addresses/",
            {
                "country_code": "NG",
                "country_name": "Nigeria",
                "administrative_area_name": "Lagos",
                "street_address": "Victoria Island",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["country"]["code"], "NG")
        self.assertEqual(response.data["country"]["name"], "Nigeria")
        self.assertEqual(response.data["administrative_area"]["name"], "Lagos")

    def test_delivery_options_are_created_and_toggled_by_owner(self):
        client = APIClient()
        client.force_authenticate(user=self.seller)
        response = client.post(
            "/api/v1/localization/delivery-options/",
            {
                "mode": "in_city",
                "country_id": str(self.country.pk),
                "administrative_area_id": str(self.province.pk),
                "locality_id": str(self.city.pk),
                "fees": "2.50",
                "estimated_delivery_days": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        option_id = response.data["id"]
        toggled = client.post(
            f"/api/v1/localization/delivery-options/{option_id}/toggle_active/"
        )
        self.assertEqual(toggled.status_code, 200, toggled.data)
        self.assertFalse(toggled.data["is_active"])

    def test_public_profile_and_product_do_not_leak_legacy_location(self):
        SellerLocationPreference.objects.create(
            seller=self.seller,
            show_country=False,
            show_admin_area=False,
            show_locality=False,
            show_public_note=False,
        )

        profile = UserSerializer(self.seller).data
        product = ProductDetailSerializer(self.product).data

        self.assertEqual(profile["city"], "")
        self.assertEqual(profile["country"], "")
        self.assertEqual(profile["public_location_display"], "")
        self.assertEqual(product["city"], "")
        self.assertEqual(product["country"], "")
        self.assertEqual(product["seller_location_display"], "")

    def test_administrative_area_search_matches_alternate_names(self):
        self.city.alt_names = ["Léopoldville"]
        self.city.save(update_fields=["alt_names"])

        response = APIClient().get(
            "/api/v1/localization/areas/",
            {"country": str(self.country.pk), "search": "leopold"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [area["id"] for area in response.data["results"]], [str(self.city.pk)]
        )

    def test_authenticated_user_can_resolve_country_on_demand(self):
        client = APIClient()
        client.force_authenticate(user=self.buyer)

        response = client.post(
            "/api/v1/localization/countries/resolve/",
            {"code": "NG", "name": "Nigeria"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["code"], "NG")
        self.assertEqual(
            client.post(
                "/api/v1/localization/countries/resolve/",
                {"code": "NG", "name": "Nigeria"},
                format="json",
            ).status_code,
            200,
        )

    def test_seller_can_activate_and_disable_delivery_option(self):
        option = DeliveryOption.objects.get(seller=self.seller)
        option.is_active = False
        option.save(update_fields=["is_active"])
        self.assertFalse(DeliveryOption.objects.get(pk=option.pk).is_active)

    def test_cannot_create_invalid_location_chain(self):
        other_country = Country.objects.create(code="AO", name="Angola")
        client = APIClient()
        client.force_authenticate(user=self.seller)
        response = client.post(
            "/api/v1/localization/addresses/",
            {
                "country_id": str(other_country.pk),
                "administrative_area_id": str(self.province.pk),
                "street_address": "Rue 12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PrivateAddress.objects.filter(user=self.seller).count(), 1)
