from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Negotiation
from .serializers import (
    CounterProposalInputSerializer,
    NegotiationSerializer,
    ProposalInputSerializer,
)
from .services import create_proposal, expire_if_stale, transition_negotiation


class NegotiationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Negotiation.objects.filter(
            Q(buyer=request.user) | Q(seller=request.user)
        ).select_related("product", "variant", "buyer", "seller").prefetch_related("events")
        for negotiation in queryset:
            expire_if_stale(negotiation)
        return Response(NegotiationSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ProposalInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        negotiation = create_proposal(
            buyer=request.user,
            product_id=serializer.validated_data["product_id"],
            variant_id=serializer.validated_data.get("variant_id"),
            amount=serializer.validated_data["amount"],
        )
        return Response(NegotiationSerializer(negotiation).data, status=status.HTTP_201_CREATED)


class NegotiationActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    action_name = None

    def post(self, request, pk):
        negotiation = Negotiation.objects.filter(
            Q(buyer=request.user) | Q(seller=request.user), pk=pk
        ).first()
        if negotiation is None:
            raise NotFound("Négociation introuvable.")
        amount = None
        if self.action_name == "counter":
            serializer = CounterProposalInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            amount = serializer.validated_data["amount"]
        negotiation = transition_negotiation(
            negotiation_id=negotiation.pk,
            actor=request.user,
            action=self.action_name,
            amount=amount,
        )
        return Response(NegotiationSerializer(negotiation).data)