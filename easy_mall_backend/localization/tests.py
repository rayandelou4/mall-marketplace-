from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from .models import AdministrativeArea, Country, DeliveryOption, PrivateAddress, SellerPublicLocation


class LocalizationBackendTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(code="CD", name="République démocratique du Congo")
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
        response = APIClient().get(f"/api/v1/localization/seller-location/{self.seller.username}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["country"]["name"], "République démocratique du Congo")
        self.assertNotIn("street_address", response.data)
        self.assertNotIn("private", response.data.get("country", {}))

    def test_private_address_is_not_visible_to_other_user(self):
        client = APIClient()
        client.force_authenticate(user=self.buyer)
        response = client.get(f"/api/v1/localization/addresses/{self.private_address.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_seller_can_activate_and_disable_delivery_option(self):
        option = DeliveryOption.objects.get(seller=self.seller)
        option.is_active = False
        option.save(update_fields=["is_active"])
        self.assertFalse(DeliveryOption.objects.get(pk=option.pk).is_active)

    def test_cannot_create_invalid_location_chain(self):
        with self.assertRaises(ValueError):
            PrivateAddress.objects.create(
                user=self.seller,
                country=self.country,
                administrative_area=self.province,
                locality=None,
                street_address="Rue 12",
            )
