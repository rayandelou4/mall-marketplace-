from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Notification


class NotificationDeletionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="notification-user@example.com",
            phone_number="+10000000031",
            username="notification-user",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            email="other-notification-user@example.com",
            phone_number="+10000000032",
            username="other-notification-user",
            password="test-password",
        )
        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NotificationType.NEW_SALE,
            title="Nouvelle commande reçue",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_owner_can_delete_notification(self):
        response = self.client.delete(
            reverse("notifications:notification-detail", kwargs={"pk": self.notification.pk})
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=self.notification.pk).exists())

    def test_user_cannot_delete_another_users_notification(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(
            reverse("notifications:notification-detail", kwargs={"pk": self.notification.pk})
        )

        self.assertEqual(response.status_code, 404)


class NotificationPreferenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="notification-preferences@mall.test",
            phone_number="+243900000033",
            username="notification-preferences",
            password="User123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_user_can_read_and_update_alert_preferences(self):
        url = reverse("notifications:preferences")
        initial = self.client.get(url)
        self.assertEqual(initial.status_code, 200)
        self.assertTrue(initial.data["price_drop_alerts"])
        self.assertTrue(initial.data["saved_search_alerts"])

        updated = self.client.patch(
            url,
            {"price_drop_alerts": False},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.data["price_drop_alerts"])
        self.assertTrue(updated.data["saved_search_alerts"])
