"""
Service de l'app `notifications`.

Point d'entrée unique utilisé par les autres apps (messaging, orders,
payments, catalog) pour créer une notification, plutôt que de manipuler le
modèle `Notification` directement partout où un événement se produit.
"""

from .models import Notification, NotificationPreference


PREFERENCE_FIELDS = {
    Notification.NotificationType.PRICE_DROP: "price_drop_alerts",
    Notification.NotificationType.SAVED_SEARCH_MATCH: "saved_search_alerts",
}


def notify(user, notification_type, title, body="", link_path=""):
    preference_field = PREFERENCE_FIELDS.get(notification_type)
    if preference_field:
        preference = NotificationPreference.objects.filter(user=user).first()
        if preference and not getattr(preference, preference_field):
            return None
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
    )


def notify_moderation_event(user, notification_type, title, body="", link_path=""):
    return notify(user, notification_type, title, body=body, link_path=link_path)
