"""
Vues de l'app `analytics`.

Pas de modèle ici : agrège des données déjà présentes dans les autres apps
pour le tableau de bord administrateur (cahier des charges §"Administration"
— "statistiques globales"). L'admin Django donne des listes filtrables par
modèle ; ceci donne la vue d'ensemble que ces listes ne donnent pas.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from moderation.models import Dispute
from orders.models import Order
from payments.models import Commission
from reviews.models import Review
from seller_verification.models import VerificationRequest, VerificationRequestStatus

User = get_user_model()


@method_decorator(never_cache, name="dispatch")
class GlobalStatsView(APIView):
    """Réservé au staff (`IsAdminUser` = `is_staff=True`, cohérent avec l'accès admin Django)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        thirty_days_ago = timezone.now() - timedelta(days=30)

        orders_by_status = {
            row["status"]: row["count"] for row in Order.objects.values("status").annotate(count=Count("id"))
        }

        commissions_by_currency = {
            row["order__currency"]: row["total"]
            for row in Commission.objects.values("order__currency").annotate(total=Sum("amount"))
        }

        gmv_by_currency = {
            row["currency"]: row["total"]
            for row in Order.objects.exclude(status=Order.Status.CANCELLED)
            .values("currency")
            .annotate(total=Sum("total_amount"))
        }

        top_categories = list(
            Product.objects.values("category__name").annotate(count=Count("id")).order_by("-count")[:5]
        )

        return Response(
            {
                "users": {
                    "total": User.objects.count(),
                    "new_last_30_days": User.objects.filter(date_joined__gte=thirty_days_ago).count(),
                    "verified": User.objects.filter(is_email_verified=True, is_phone_verified=True).count(),
                },
                "sellers": {
                    "individual": Product.objects.filter(
                        seller__seller_type=User.SellerType.INDIVIDUAL
                    ).values("seller_id").distinct().count(),
                    "professional": Product.objects.filter(
                        seller__seller_type=User.SellerType.PROFESSIONAL
                    ).values("seller_id").distinct().count(),
                },
                "products": {
                    "total": Product.objects.count(),
                    "published": Product.objects.filter(status=Product.Status.PUBLISHED).count(),
                    "active_listings": Product.objects.filter(
                        status=Product.Status.PUBLISHED, is_suspended=False
                    ).count(),
                    "pending_moderation": Product.objects.filter(
                        moderation_status=Product.ModerationStatus.PENDING
                    ).count(),
                    "sold": Product.objects.filter(status=Product.Status.SOLD).count(),
                },
                "verification": {
                    "pending": VerificationRequest.objects.filter(
                        status__in=[
                            VerificationRequestStatus.PENDING,
                            VerificationRequestStatus.UNDER_REVIEW,
                        ]
                    ).count(),
                },
                "orders": {
                    "total": Order.objects.count(),
                    "by_status": orders_by_status,
                },
                "revenue": {
                    "commissions_by_currency": commissions_by_currency,
                    "gmv_by_currency": gmv_by_currency,
                },
                "moderation": {
                    "open_disputes": Dispute.objects.filter(
                        status__in=[
                            Dispute.Status.OPEN,
                            Dispute.Status.WAITING_SELLER,
                            Dispute.Status.WAITING_BUYER,
                            Dispute.Status.UNDER_REVIEW,
                        ]
                    ).count(),
                },
                "reviews": {
                    "total": Review.objects.filter(moderation_status=Review.ModerationStatus.APPROVED).count(),
                },
                "top_categories": top_categories,
            }
        )
