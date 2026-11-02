"""
Vues de l'app `payments`.
"""

from django.conf import settings
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, PaymentProvider, SupportedMarket, Wallet
from .serializers import (
    PaymentConfirmSerializer,
    PaymentInitiateSerializer,
    PaymentProviderSerializer,
    PaymentSerializer,
    SupportedMarketSerializer,
    WalletSerializer,
)


class SupportedMarketViewSet(viewsets.ReadOnlyModelViewSet):
    """Pays où Mall est disponible — le frontend s'en sert pour proposer les bons moyens de paiement."""

    queryset = SupportedMarket.objects.filter(is_active=True)
    serializer_class = SupportedMarketSerializer
    permission_classes = [permissions.AllowAny]


class PaymentProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Moyens de paiement actifs, filtrables par marché : GET /providers/?market=<id>"""

    serializer_class = PaymentProviderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = PaymentProvider.objects.filter(is_active=True).select_related("market")
        market_id = self.request.query_params.get("market")
        if market_id:
            # Un vendeur/acheteur d'un marché donné voit ses moyens locaux
            # (Mobile Money) + les moyens globaux (Stripe/PayPal, market=null).
            from django.db.models import Q

            queryset = queryset.filter(Q(market_id=market_id) | Q(market__isnull=True))
        return queryset


class PaymentListView(generics.ListAPIView):
    """Historique des paiements de l'acheteur connecté."""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(order__buyer=self.request.user).select_related(
            "provider", "order"
        )


class PaymentConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "mode": settings.PAYMENTS_MODE,
            "mobile_money_coming_soon": settings.PAYMENTS_MODE != "online",
        })


class PaymentInitiateView(APIView):
    """Démarre un paiement pour une commande de l'acheteur connecté."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if settings.PAYMENTS_MODE == "cash":
            return Response(
                {"detail": "Le paiement en ligne n'est pas encore disponible."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaymentInitiateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        # TODO : appeler ici l'adaptateur du fournisseur (`payment.provider.code`)
        # pour déclencher réellement le paiement (redirection USSD, session Stripe...).
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentConfirmView(APIView):
    """
    Webhook de confirmation appelé par le fournisseur de paiement (pas par
    l'acheteur directement).

    ⚠️ Sécurité : en production, remplacer `AllowAny` par une vérification de
    la signature du webhook (HMAC fourni par le fournisseur) — ne jamais se
    fier à l'IP ou au corps de la requête seuls pour authentifier un webhook.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if settings.PAYMENTS_MODE == "cash":
            return Response(
                {"detail": "Le paiement en ligne n'est pas encore disponible."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(PaymentSerializer(payment).data)


class WalletView(APIView):
    """Portefeuille de l'utilisateur connecté — revenus du vendeur (tableau de bord)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet, _created = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)
