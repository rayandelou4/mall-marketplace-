"""
Modèle de l'app `reviews`.

Un avis est toujours rattaché à une commande (`order`) pour garantir qu'il
provient d'un achat réel — voir la validation dans ReviewCreateSerializer
(uniquement après confirmation de réception, `Order.Status.DELIVERED`).
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    class ModerationStatus(models.TextChoices):
        PENDING = "pending", _("En attente")
        APPROVED = "approved", _("Approuvé")
        REJECTED = "rejected", _("Rejeté")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    reviewed_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews"
    )
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="reviews")

    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    # Pas de file de modération construite pour l'instant (voir §"Administration"
    # jamais bâtie) : les avis sont auto-approuvés à la création.
    moderation_status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.APPROVED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reviewer", "order", "reviewed_user"], name="one_review_per_seller_per_order"
            )
        ]

    def __str__(self):
        return f"{self.rating}★ — {self.reviewer} → {self.reviewed_user}"
