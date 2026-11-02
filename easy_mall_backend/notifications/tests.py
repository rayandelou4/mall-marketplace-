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
