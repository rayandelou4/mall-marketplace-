"""
Service de l'app `notifications`.

Point d'entrée unique utilisé par les autres apps (messaging, orders,
payments, catalog) pour créer une notification, plutôt que de manipuler le
modèle `Notification` directement partout où un événement se produit.
"""

from .models import Notification


def notify(user, notification_type, title, body="", link_path=""):
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
    )


def notify_moderation_event(user, notification_type, title, body="", link_path=""):
    return notify(user, notification_type, title, body=body, link_path=link_path)
