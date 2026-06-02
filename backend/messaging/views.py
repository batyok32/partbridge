from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Message, Thread
from .serializers import MessageSerializer, StartThreadSerializer, ThreadSerializer


class ThreadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        threads = Thread.objects.filter(
            Q(buyer=request.user) | Q(seller=request.user)
        ).prefetch_related("messages")
        return Response(ThreadSerializer(threads, many=True, context={"request": request}).data)


class StartThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from parts.models import Item

        ser = StartThreadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item_id = ser.validated_data["item_id"]
        body = ser.validated_data["body"]
        item = get_object_or_404(Item, pk=item_id)
        seller = item.vehicle.seller
        if request.user == seller:
            return Response({"detail": "You cannot message yourself."}, status=status.HTTP_400_BAD_REQUEST)

        thread, created = Thread.objects.get_or_create(
            buyer=request.user,
            seller=seller,
            item=item,
        )
        msg = Message.objects.create(thread=thread, sender=request.user, body=body)
        thread.last_message_at = timezone.now()
        thread.save(update_fields=["last_message_at"])
        return Response(ThreadSerializer(thread, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        thread = get_object_or_404(
            Thread.objects.prefetch_related("messages"),
            pk=thread_id,
        )
        if request.user not in (thread.buyer, thread.seller):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ThreadSerializer(thread, context={"request": request}).data)


class ThreadMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        thread = get_object_or_404(Thread, pk=thread_id)
        if request.user not in (thread.buyer, thread.seller):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        messages = thread.messages.all()
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, thread_id):
        thread = get_object_or_404(Thread, pk=thread_id)
        if request.user not in (thread.buyer, thread.seller):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        ser = MessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        msg = ser.save(thread=thread, sender=request.user)
        thread.last_message_at = timezone.now()
        thread.save(update_fields=["last_message_at"])
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class ThreadMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(Thread, pk=thread_id)
        if request.user not in (thread.buyer, thread.seller):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        updated = thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        return Response({"marked_read": updated})
