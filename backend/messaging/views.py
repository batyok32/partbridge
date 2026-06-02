from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from messaging.serializers import (
    BulkRfqSerializer,
    MarkReadSerializer,
    QuoteSerializer,
    SendMessageSerializer,
    StartThreadSerializer,
    ThreadDetailSerializer,
    ThreadSerializer,
    thread_for_user_qs,
)
from vehicles.models import VehiclePart

from .models import Message, Quote, Thread


def _assert_buyer(user, seller_id: int) -> None:
    if user.id == seller_id:
        raise ValueError("You cannot message your own listing.")


def _upsert_thread(*, buyer, seller, vehicle_part):
    thread, _created = Thread.objects.get_or_create(
        buyer=buyer,
        seller=seller,
        vehicle_part=vehicle_part,
        defaults={
            "subject": vehicle_part.label,
            "buyer_last_read_at": timezone.now(),
        },
    )
    return thread


class ThreadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = thread_for_user_qs(request.user).prefetch_related("messages", "quotes")
        ser = ThreadSerializer(qs, many=True, context={"request": request})
        return Response(ser.data)


class StartThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = StartThreadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        part = get_object_or_404(
            VehiclePart.objects.select_related("vehicle"),
            pk=ser.validated_data["vehicle_part_id"],
        )
        buyer = request.user
        seller = part.vehicle.owner
        try:
            _assert_buyer(buyer, seller.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            thread = _upsert_thread(buyer=buyer, seller=seller, vehicle_part=part)
            body = (ser.validated_data.get("message") or "").strip()
            if body:
                Message.objects.create(thread=thread, sender=buyer, body=body)
                thread.seller_last_read_at = None
                thread.buyer_last_read_at = timezone.now()
                thread.touch_from_message(body)
                thread.save(update_fields=["buyer_last_read_at", "seller_last_read_at", "updated_at"])
        detail = ThreadDetailSerializer(
            thread_for_user_qs(request.user).prefetch_related("messages", "quotes").get(pk=thread.pk),
            context={"request": request},
        )
        return Response(detail.data, status=status.HTTP_201_CREATED)


class BulkRfqView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = BulkRfqSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = ser.validated_data["message"].strip()
        created_ids = []
        skipped = 0
        with transaction.atomic():
            for part_id in ser.validated_data["vehicle_part_ids"]:
                part = (
                    VehiclePart.objects.select_related("vehicle")
                    .filter(pk=part_id, is_removed=False)
                    .first()
                )
                if not part:
                    skipped += 1
                    continue
                seller = part.vehicle.owner
                try:
                    _assert_buyer(request.user, seller.id)
                except ValueError:
                    skipped += 1
                    continue
                thread = _upsert_thread(buyer=request.user, seller=seller, vehicle_part=part)
                Message.objects.create(thread=thread, sender=request.user, body=body)
                thread.seller_last_read_at = None
                thread.buyer_last_read_at = timezone.now()
                thread.touch_from_message(body)
                thread.save(update_fields=["buyer_last_read_at", "seller_last_read_at", "updated_at"])
                created_ids.append(thread.id)
        return Response(
            {
                "threads_created": len(created_ids),
                "thread_ids": created_ids,
                "skipped": skipped,
            },
            status=status.HTTP_201_CREATED,
        )


class ThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id: int):
        thread = get_object_or_404(
            thread_for_user_qs(request.user).prefetch_related("messages__sender", "quotes"),
            pk=thread_id,
        )
        ser = ThreadDetailSerializer(thread, context={"request": request})
        return Response(ser.data)


class ThreadMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, thread_id: int):
        thread = get_object_or_404(
            thread_for_user_qs(request.user).prefetch_related("messages__sender"),
            pk=thread_id,
        )
        ser = ThreadDetailSerializer(thread, context={"request": request})
        return Response({"thread_id": thread.id, "messages": ser.data["messages"]})

    def post(self, request, thread_id: int):
        thread = get_object_or_404(thread_for_user_qs(request.user), pk=thread_id)
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = (ser.validated_data.get("body") or "").strip()
        image = ser.validated_data.get("image")
        msg = Message.objects.create(
            thread=thread,
            sender=request.user,
            body=body,
            image=image,
        )
        preview = body or "[image]"
        if request.user.id == thread.buyer_id:
            thread.buyer_last_read_at = timezone.now()
            thread.seller_last_read_at = None
        else:
            thread.seller_last_read_at = timezone.now()
            thread.buyer_last_read_at = None
        thread.touch_from_message(preview)
        thread.save(update_fields=["buyer_last_read_at", "seller_last_read_at", "updated_at"])

        # Email notification if counterparty is offline (simple: always notify)
        _notify_new_message_if_offline(thread, msg, sender=request.user)

        from messaging.serializers import MessageSerializer
        return Response(
            {"message": MessageSerializer(msg, context={"request": request}).data},
            status=201,
        )


def _notify_new_message_if_offline(thread, message, sender):
    """Send email to the other party if they haven't recently read the thread."""
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        now = timezone.now()
        if sender.id == thread.buyer_id:
            recipient = thread.seller
            last_read = thread.seller_last_read_at
        else:
            recipient = thread.buyer
            last_read = thread.buyer_last_read_at

        # If they read within the last 2 minutes, they're likely online — skip email
        if last_read and (now - last_read).total_seconds() < 120:
            return

        part_label = thread.vehicle_part.label if thread.vehicle_part else "a listing"
        body_preview = message.body[:200] if message.body else "(image attached)"
        send_mail(
            subject=f"New message from {sender.name or sender.email} — Partbridge",
            message=(
                f"You have a new message regarding: {part_label}\n\n"
                f"{sender.name or sender.email}: {body_preview}\n\n"
                f"Reply in your inbox: {settings.FRONTEND_BASE_URL}/inbox"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    except Exception:
        pass


class ThreadMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id: int):
        thread = get_object_or_404(thread_for_user_qs(request.user), pk=thread_id)
        ser = MarkReadSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        marked_at = ser.validated_data.get("marked_at") or timezone.now()
        if request.user.id == thread.buyer_id:
            thread.buyer_last_read_at = marked_at
            thread.save(update_fields=["buyer_last_read_at", "updated_at"])
        else:
            thread.seller_last_read_at = marked_at
            thread.save(update_fields=["seller_last_read_at", "updated_at"])
        return Response({"detail": "Marked as read."})


class ThreadQuoteCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id: int):
        thread = get_object_or_404(thread_for_user_qs(request.user), pk=thread_id)
        if request.user.id != thread.seller_id:
            return Response({"detail": "Only the seller can send a quote."}, status=403)
        if not thread.vehicle_part:
            return Response({"detail": "Quote requires a part-bound thread."}, status=400)
        if thread.vehicle_part.effective_listing_state != thread.vehicle_part.ListingState.BUY_NOW:
            return Response({"detail": "Part must be Buy Now before sending quote."}, status=400)
        ser = QuoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        quote = Quote.objects.create(
            thread=thread,
            seller=request.user,
            vehicle_part=thread.vehicle_part,
            price=ser.validated_data["price"],
            note=ser.validated_data.get("note", ""),
        )
        part = thread.vehicle_part
        part.offer_price_usd = quote.price
        part.offer_expires_at = timezone.now() + timedelta(days=2)
        part.offer_source_quote = quote
        part.save(
            update_fields=["offer_price_usd", "offer_expires_at", "offer_source_quote", "updated_at"]
        )
        system_line = (
            f"Offer price ${quote.price} is now the public Buy Now price for 48 hours. "
            "Buyers purchase from the listing page."
        )
        Message.objects.create(
            thread=thread,
            sender=request.user,
            body=system_line,
            is_system=True,
        )
        thread.buyer_last_read_at = None
        thread.seller_last_read_at = timezone.now()
        thread.touch_from_message(system_line)
        thread.save(update_fields=["buyer_last_read_at", "seller_last_read_at", "updated_at"])
        return Response(QuoteSerializer(quote).data, status=201)
