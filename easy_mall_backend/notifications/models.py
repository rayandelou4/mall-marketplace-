"""
Modèle de l'app `notifications`.

`link_path` est volontairement une simple route frontend (ex. "/mes-commandes")
plutôt qu'une relation générique (GenericForeignKey) vers l'objet concerné :
plus simple à créer, plus simple à consommer côté frontend (`navigate(link_path)`),
pas de dépendance à `django.contrib.contenttypes`.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_MESSAGE = "new_message", _("Nouveau message")
        NEW_SALE = "new_sale", _("Nouvelle vente")
        PAYMENT_RECEIVED = "payment_received", _("Paiement reçu")
        SHIPPING = "shipping", _("Expédition")
        DELIVERY = "delivery", _("Livraison")
        NEW_FAVORITE = "new_favorite", _("Nouveau favori")
        PROMOTION = "promotion", _("Promotion")
        PRICE_DROP = "price_drop", _("Baisse de prix")
        SAVED_SEARCH_MATCH = "saved_search_match", _("Nouvelle annonce correspondant à une recherche")
        PRODUCT_REPORTED = "product_reported", _("Annonce signalée")
        REPORT_DECISION = "report_decision", _("Décision de modération")
        DISPUTE_OPENED = "dispute_opened", _("Litige ouvert")
        DISPUTE_UPDATE = "dispute_update", _("Mise à jour du litige")
        DISPUTE_RESOLVED = "dispute_resolved", _("Litige résolu")
        LISTING_SUSPENDED = "listing_suspended", _("Annonce suspendue")
        VERIFICATION_UPDATE = "verification_update", _("Mise à jour de vérification")
        SUBSCRIPTION_CONFIRMED = "subscription_confirmed", _("Abonnement confirmé")
        SUBSCRIPTION_PAYMENT_FAILED = "subscription_payment_failed", _("Paiement d'abonnement échoué")
        SUBSCRIPTION_EXPIRING = "subscription_expiring", _("Abonnement bientôt expiré")
        SUBSCRIPTION_EXPIRED = "subscription_expired", _("Abonnement expiré")
        SUBSCRIPTION_CANCELLED = "subscription_cancelled", _("Abonnement annulé")
        SUBSCRIPTION_RENEWED = "subscription_renewed", _("Abonnement renouvelé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices)
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    link_path = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notification_type_display()} — {self.user}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    price_drop_alerts = models.BooleanField(default=True)
    saved_search_alerts = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"

    def __str__(self):
        return f"Préférences de notification — {self.user}"
