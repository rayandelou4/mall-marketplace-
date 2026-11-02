from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework.test import APITestCase

from .models import EmailVerificationToken, User
from .serializers import RegisterSerializer


class RegisterSerializerEmailTests(TestCase):
    def test_registration_saves_avatar_url(self):
        payload = {
            "email": "avatar@example.com",
            "phone_number": "+33606070810",
            "username": "avatar-user",
            "first_name": "Avatar",
            "last_name": "User",
            "avatar_url": "https://res.cloudinary.com/demo/image/upload/avatar.jpg",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "seller_type": "individual",
        }

        with patch("accounts.serializers.send_verification_email_task.run"):
            serializer = RegisterSerializer(data=payload)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            user = serializer.save()

        self.assertEqual(user.avatar_url, payload["avatar_url"])
        self.assertEqual(user.seller_type, "individual")

    def test_registration_rejects_invalid_seller_type(self):
        payload = {
            "email": "seller-type@example.com",
            "phone_number": "+33606070811",
            "username": "seller-type",
            "first_name": "Seller",
            "last_name": "Type",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "seller_type": "admin",
        }

        with patch("accounts.serializers.send_verification_email_task.run"):
            serializer = RegisterSerializer(data=payload)
            self.assertFalse(serializer.is_valid())
            self.assertIn("seller_type", serializer.errors)

    def test_registration_fails_when_verification_email_cannot_be_sent(self):
        payload = {
            "email": "alice@example.com",
            "phone_number": "+33601020304",
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Dupont",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }

        with patch("accounts.tasks.send_mail", side_effect=Exception("SMTP failed")):
            serializer = RegisterSerializer(data=payload)
            with self.assertRaises(serializers.ValidationError):
                serializer.is_valid(raise_exception=True)
                serializer.save()

        self.assertFalse(User.objects.filter(email="alice@example.com").exists())

    def test_registration_creates_six_digit_verification_code(self):
        payload = {
            "email": "bob@example.com",
            "phone_number": "+33606070809",
            "username": "bob",
            "first_name": "Bob",
            "last_name": "Martin",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "seller_type": "professional",
        }

        with patch("accounts.serializers.send_verification_email_task.run") as send_email:
            serializer = RegisterSerializer(data=payload)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            user = serializer.save()

        token = EmailVerificationToken.objects.get(user=user)
        self.assertEqual(len(token.code), 6)
        self.assertTrue(token.code.isdigit())
        self.assertIn(token.code, str(send_email.call_args[0][-1]))


class SellerPublicProfileTests(APITestCase):
    def test_public_profile_does_not_expose_private_fields(self):
        user = User.objects.create_user(
            email="public@example.com",
            phone_number="+243812345678",
            username="public-user",
            password="StrongPass123!",
            is_email_verified=True,
            is_active=True,
            seller_type="individual",
        )

        response = self.client.get(reverse("accounts:public-profile", kwargs={"username": user.username}))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("phone_number", response.data)
        self.assertNotIn("email", response.data)
        self.assertEqual(response.data["seller_type"], "individual")
