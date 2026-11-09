"""
Vues de l'app `analytics`.

Pas de modèle ici : agrège des données déjà présentes dans les autres apps
pour le tableau de bord administrateur (cahier des charges §"Administration"
— "statistiques globales"). L'admin Django donne des listes filtrables par
modèle ; ceci donne la vue d'ensemble que ces listes ne donnent pas.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product, ProductActivity, ProductVariant
from moderation.models import Dispute, MessageReport, ProductReport
from orders.models import Order, OrderItem
from payments.models import Commission, Payment
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
            for row in Order.objects.filter(status=Order.Status.DELIVERED)
            .values("currency")
            .annotate(total=Sum("total_amount"))
        }

        sellers_by_type = {
            row["seller_type"]: row["count"]
            for row in User.objects.filter(
                products__status=Product.Status.PUBLISHED,
                products__moderation_status=Product.ModerationStatus.APPROVED,
                products__is_suspended=False,
            )
            .values("seller_type")
            .annotate(count=Count("id", distinct=True))
        }

        top_categories = list(
            Product.objects.values("category__name").annotate(count=Count("id")).order_by("-count")[:5]
        )

        return Response(
            {
                "users": {
                    "total": User.objects.count(),
                    "new_last_30_days": User.objects.filter(date_joined__gte=thirty_days_ago).count(),
                    "verified": User.objects.filter(is_email_verified=True).count(),
                },
                "sellers": {
                    "individual": sellers_by_type.get(User.SellerType.INDIVIDUAL, 0),
                    "professional": sellers_by_type.get(User.SellerType.PROFESSIONAL, 0),
                },
                "products": {
                    "total": Product.objects.count(),
                    "published": Product.objects.filter(status=Product.Status.PUBLISHED).count(),
                    "active_listings": Product.objects.filter(
                        status=Product.Status.PUBLISHED,
                        moderation_status=Product.ModerationStatus.APPROVED,
                        is_suspended=False,
                        stock_quantity__gt=0,
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
                    "open_product_reports": ProductReport.objects.filter(
                        status__in=[ProductReport.Status.NEW, ProductReport.Status.UNDER_REVIEW]
                    ).count(),
                    "high_risk_product_reports": ProductReport.objects.filter(
                        is_high_risk=True,
                        status__in=[ProductReport.Status.NEW, ProductReport.Status.UNDER_REVIEW],
                    ).count(),
                    "open_message_reports": MessageReport.objects.filter(
                        status__in=[MessageReport.Status.NEW, MessageReport.Status.UNDER_REVIEW]
                    ).count(),
                    "suspended_accounts": User.objects.filter(is_suspended=True).count(),
                },
                "reviews": {
                    "total": Review.objects.filter(
                        moderation_status=Review.ModerationStatus.APPROVED
                    ).count(),
                },
                "top_categories": top_categories,
            }
        )


class SellerStatsView(APIView):
    """Statistiques commerciales réelles, limitées au vendeur authentifié."""

    permission_classes = [permissions.IsAuthenticated]
    periods = {
        "daily": (30, TruncDay),
        "weekly": (84, TruncWeek),
        "monthly": (365, TruncMonth),
        "yearly": (1825, TruncYear),
    }

    def get(self, request):
        period = request.query_params.get("period", "weekly")
        if period not in self.periods:
            return Response(
                {"period": "Choisissez daily, weekly, monthly ou yearly."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        days, truncation = self.periods[period]
        start = timezone.now() - timedelta(days=days)
        products = Product.objects.filter(seller=request.user)
        delivered_items = OrderItem.objects.filter(
            seller=request.user,
            order__status=Order.Status.DELIVERED,
        )
        line_revenue = ExpressionWrapper(
            F("unit_price") * F("quantity") + F("shipping_cost"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

        revenue_by_currency = list(
            delivered_items.values("order__currency")
            .annotate(total=Sum(line_revenue))
            .order_by("order__currency")
        )
        series = list(
            delivered_items.filter(order__created_at__gte=start)
            .annotate(
                bucket=truncation(
                    "order__created_at", tzinfo=timezone.get_current_timezone()
                )
            )
            .values("bucket")
            .annotate(
                orders=Count("order_id", distinct=True),
                units=Sum("quantity"),
                revenue=Sum(line_revenue),
            )
            .order_by("bucket")
        )
        revenue_series = list(
            delivered_items.filter(order__created_at__gte=start)
            .annotate(
                bucket=truncation(
                    "order__created_at", tzinfo=timezone.get_current_timezone()
                )
            )
            .values("bucket", "order__currency")
            .annotate(revenue=Sum(line_revenue))
            .order_by("bucket", "order__currency")
        )
        reviews = Review.objects.filter(
            reviewed_user=request.user,
            moderation_status=Review.ModerationStatus.APPROVED,
        ).aggregate(average=Avg("rating"), count=Count("id"))
        top_selling = list(
            delivered_items.values("product_id", "product_title", "order__currency")
            .annotate(units=Sum("quantity"), revenue=Sum(line_revenue))
            .order_by("-units", "product_title")[:5]
        )
        top_viewed = list(
            products.order_by("-views_count", "title")
            .values("id", "title", "views_count", "favorites_count")[:5]
        )
        product_totals = products.aggregate(
            count=Count("id"),
            published=Count("id", filter=Q(status=Product.Status.PUBLISHED)),
            low_stock=Count(
                "id",
                filter=Q(stock_quantity__gt=0, stock_quantity__lte=3),
            ),
            views=Sum("views_count"),
            favorites=Sum("favorites_count"),
        )
        variant_totals = ProductVariant.objects.filter(product__seller=request.user).aggregate(
            low_stock=Count("id", filter=Q(stock_quantity__gt=0, stock_quantity__lte=3)),
            out_of_stock=Count("id", filter=Q(stock_quantity=0)),
        )
        delivered_order_ids = delivered_items.values("order_id").distinct()
        period_visitors = ProductActivity.objects.filter(
            product__seller=request.user,
            activity_type=ProductActivity.ActivityType.VIEW,
            created_at__gte=start,
        ).values("visitor_id")
        period_delivered_items = delivered_items.filter(order__created_at__gte=start)
        converted_visitors = period_delivered_items.filter(
            conversion_visitor_id__in=period_visitors
        ).values_list("conversion_visitor_id", flat=True).distinct().count()
        visitor_count = period_visitors.distinct().count()
        cart_adds = ProductActivity.objects.filter(
            product__seller=request.user,
            activity_type=ProductActivity.ActivityType.CART_ADD,
            created_at__gte=start,
        ).count()
        seller_orders = Order.objects.filter(items__seller=request.user).distinct()
        seller_payments = list(
            Payment.objects.filter(order__items__seller=request.user)
            .values("id", "status", "amount", "currency")
            .distinct()
        )
        pending_payment_totals = {}
        for payment in seller_payments:
            if payment["status"] in {Payment.Status.PENDING, Payment.Status.HELD_ESCROW}:
                currency = payment["currency"]
                pending_payment_totals[currency] = (
                    pending_payment_totals.get(currency, Decimal("0.00"))
                    + payment["amount"]
                )

        return Response(
            {
                "period": period,
                "products": {
                    "total": product_totals["count"] or 0,
                    "published": product_totals["published"] or 0,
                    "low_stock": product_totals["low_stock"] or 0,
                    "low_stock_variants": variant_totals["low_stock"] or 0,
                    "out_of_stock_variants": variant_totals["out_of_stock"] or 0,
                    "views": product_totals["views"] or 0,
                    "favorites": product_totals["favorites"] or 0,
                    "cart_adds": cart_adds,
                },
                "sales": {
                    "units": delivered_items.aggregate(total=Sum("quantity"))["total"] or 0,
                    "products_sold": delivered_items.exclude(product_id__isnull=True).values("product_id").distinct().count(),
                    "orders": Order.objects.filter(pk__in=delivered_order_ids).count(),
                    "orders_received": seller_orders.count(),
                    "orders_pending": seller_orders.filter(
                        status__in=[Order.Status.PENDING, Order.Status.PAID, Order.Status.SHIPPED]
                    ).count(),
                    "revenue_by_currency": [
                        {"currency": row["order__currency"], "amount": row["total"]}
                        for row in revenue_by_currency
                    ],
                    "series": [
                        {
                            "date": row["bucket"],
                            "orders": row["orders"],
                            "units": row["units"],
                            "revenue": row["revenue"],
                        }
                        for row in series
                    ],
                    "revenue_series": [
                        {
                            "date": row["bucket"],
                            "currency": row["order__currency"],
                            "revenue": row["revenue"],
                        }
                        for row in revenue_series
                    ],
                    "top_products": top_selling,
                    "top_viewed": top_viewed,
                },
                "transactions": {
                    "successful": seller_orders.filter(
                        status=Order.Status.DELIVERED,
                        payment_method=Order.PaymentMethod.CASH,
                    ).count()
                    + sum(
                        payment["status"] == Payment.Status.COMPLETED
                        for payment in seller_payments
                    ),
                    "pending": sum(
                        payment["status"] in {Payment.Status.PENDING, Payment.Status.HELD_ESCROW}
                        for payment in seller_payments
                    ),
                    "pending_by_currency": [
                        {"currency": currency, "amount": amount}
                        for currency, amount in sorted(pending_payment_totals.items())
                    ],
                },
                "reviews": {
                    "count": reviews["count"],
                    "average": reviews["average"] or Decimal("0.00"),
                },
                "conversion_rate": (
                    round(converted_visitors / visitor_count * 100, 2)
                    if visitor_count
                    else None
                ),
            }
        )

