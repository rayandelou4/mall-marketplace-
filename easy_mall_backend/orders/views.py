"""
Vues de l'app `orders`.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify
from payments.services import release_order_payment

from .models import Order, OrderItem
from .serializers import (
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderListSerializer,
)


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Commandes de l'acheteur connecté. Pas d'update/delete direct : le statut
    évolue uniquement via l'action `cancel` ou via les webhooks de paiement
    (app `payments`).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            buyer=self.request.user, hidden_by_buyer=False
        ).prefetch_related("items")

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status not in (Order.Status.DELIVERED, Order.Status.CANCELLED):
            return Response(
                {"detail": "Seules les commandes livrées ou annulées peuvent être retirées de la liste."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.hidden_by_buyer = True
        order.save(update_fields=["hidden_by_buyer"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        if self.action == "create":
            return OrderCreateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        serializer = OrderCancelSerializer(data={}, context={"order": order})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def confirm_receipt(self, request, pk=None):
        """Confirme la remise en main propre ou libère le paiement en mode online."""
        order = self.get_object()
        if settings.PAYMENTS_MODE == "online" and order.payment_method != Order.PaymentMethod.CASH:
            try:
                release_order_payment(order)
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(OrderDetailSerializer(order).data)

        if settings.PAYMENTS_MODE == "online":
            if order.status != Order.Status.SHIPPED:
                return Response(
                    {"detail": "La commande doit être expédiée avant de confirmer sa réception."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = Order.Status.DELIVERED
            order.save(update_fields=["status"])
            return Response(OrderDetailSerializer(order).data)

        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": "Seule une commande en attente de remise peut être confirmée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seller_ids = list(order.items.values_list("seller_id", flat=True).distinct())
        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])
        User.objects.filter(pk=order.buyer_id).update(total_purchases=F("total_purchases") + 1)
        User.objects.filter(pk__in=seller_ids).update(total_sales=F("total_sales") + 1)
        for seller in User.objects.filter(pk__in=seller_ids):
            notify(
                seller,
                Notification.NotificationType.DELIVERY,
                "Remise confirmée",
                f"L’acheteur a confirmé la remise de la commande {order.id}.",
                "/vendeur",
            )
        return Response(OrderDetailSerializer(order).data)


class SellerSalesViewSet(
    mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    """Lignes de commande vendues par l'utilisateur connecté — tableau de bord vendeur."""

    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return OrderItem.objects.filter(
            seller=self.request.user, hidden_by_seller=False
        ).select_related(
            "order", "product"
        )

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        if item.order.status not in (Order.Status.DELIVERED, Order.Status.CANCELLED):
            return Response(
                {"detail": "Seules les ventes livrées ou annulées peuvent être retirées de la liste."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.hidden_by_seller = True
        item.save(update_fields=["hidden_by_seller"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="confirmed-count")
    def confirmed_count(self, request):
        count = OrderItem.objects.filter(
            seller=request.user, order__status=Order.Status.DELIVERED
        ).count()
        return Response({"count": count})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def mark_shipped(self, request, pk=None):
        """Le vendeur signale l'expédition d'une ligne d'une commande cash."""
        if settings.PAYMENTS_MODE == "cash":
            return Response(
                {"detail": "Les commandes sont confirmées par l’acheteur après la remise en main propre."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item = self.get_queryset().select_for_update().get(pk=pk)
        order = Order.objects.select_for_update().get(pk=item.order_id)
        if order.payment_method != Order.PaymentMethod.CASH:
            return Response(
                {"detail": "Le signalement d'expédition est réservé aux commandes en espèces."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status not in (Order.Status.PENDING, Order.Status.SHIPPED):
            return Response(
                {"detail": "Cette commande ne peut plus être expédiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not item.is_shipped:
            item.is_shipped = True
            item.save(update_fields=["is_shipped"])
        if not order.items.filter(is_shipped=False).exists():
            order.status = Order.Status.SHIPPED
            order.save(update_fields=["status"])
        return Response(OrderItemSerializer(item).data)
