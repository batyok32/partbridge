from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CartItem, Dispute, DisputeMessage, Order, SellerReview
from .serializers import (
    CartItemSerializer,
    DisputeMessageSerializer,
    DisputeSerializer,
    OrderSerializer,
    SellerReviewSerializer,
)


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related("item")
        return Response(CartItemSerializer(items, many=True).data)

    def post(self, request):
        ser = CartItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item_id = ser.validated_data["item"].id
        obj, created = CartItem.objects.get_or_create(
            user=request.user,
            item_id=item_id,
        )
        return Response(CartItemSerializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CartItemDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        cart_item = get_object_or_404(CartItem, pk=item_id, user=request.user)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related("order_items")


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related("order_items")


class DisputeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        disputes = Dispute.objects.filter(buyer=request.user).prefetch_related("messages")
        return Response(DisputeSerializer(disputes, many=True).data)

    def post(self, request, order_item_id):
        from orders.models import OrderItem

        order_item = get_object_or_404(OrderItem, pk=order_item_id, order__buyer=request.user)
        ser = DisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        seller = order_item.order.order_items.first()
        dispute = ser.save(
            order_item=order_item,
            buyer=request.user,
            seller=order_item.item.vehicle.seller,
        )
        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


class DisputeDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DisputeSerializer

    def get_queryset(self):
        return Dispute.objects.filter(buyer=self.request.user).prefetch_related("messages")


class DisputeMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, dispute_id):
        dispute = get_object_or_404(
            Dispute,
            pk=dispute_id,
        )
        if request.user not in (dispute.buyer, dispute.seller) and not request.user.is_staff:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        ser = DisputeMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if request.user == dispute.buyer:
            role = DisputeMessage.SenderRole.BUYER
        elif request.user == dispute.seller:
            role = DisputeMessage.SenderRole.SELLER
        else:
            role = DisputeMessage.SenderRole.SUPPORT
        msg = ser.save(dispute=dispute, sender=request.user, sender_role=role)
        return Response(DisputeMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class SellerReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_item_id):
        from orders.models import OrderItem

        order_item = get_object_or_404(OrderItem, pk=order_item_id, order__buyer=request.user)
        ser = SellerReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        review = ser.save(
            order_item=order_item,
            buyer=request.user,
            seller=order_item.item.vehicle.seller,
        )
        return Response(SellerReviewSerializer(review).data, status=status.HTTP_201_CREATED)
