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
        PRODUCT_REPORTED = "product_reported", _("Annonce signalée")
        REPORT_DECISION = "report_decision", _("Décision de modération")
        DISPUTE_OPENED = "dispute_opened", _("Litige ouvert")
        DISPUTE_RESOLVED = "dispute_resolved", _("Litige résolu")
        LISTING_SUSPENDED = "listing_suspended", _("Annonce suspendue")
        VERIFICATION_UPDATE = "verification_update", _("Mise à jour de vérification")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
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
