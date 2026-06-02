from __future__ import annotations

import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .payment_completion import finalize_order_payment

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    Stripe sends signed POSTs with a raw JSON body. No JWT; verification uses Stripe-Signature.
    Dashboard / CLI: point endpoint to .../api/v1/orders/payments/stripe/webhook/
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = (getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
        if not secret:
            logger.warning("Stripe webhook received but STRIPE_WEBHOOK_SECRET is not set.")
            return Response({"detail": "Webhook endpoint not configured."}, status=503)

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        if not sig_header:
            return Response({"detail": "Missing Stripe-Signature header."}, status=400)

        try:
            import stripe  # type: ignore
        except ImportError:
            return Response({"detail": "Stripe SDK not installed."}, status=503)

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except ValueError as exc:
            logger.warning("Stripe webhook invalid payload: %s", exc)
            return Response({"detail": "Invalid payload."}, status=400)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Stripe webhook invalid signature: %s", exc)
            return Response({"detail": "Invalid signature."}, status=400)

        etype = event.get("type") or ""
        if etype == "checkout.session.completed":
            return self._on_checkout_session_completed(event)
        if etype == "payment_intent.succeeded":
            return self._on_payment_intent_succeeded(event)
        if etype == "payment_intent.payment_failed":
            obj = (event.get("data") or {}).get("object") or {}
            logger.info(
                "Stripe payment_intent.payment_failed id=%s last_payment_error=%s",
                obj.get("id"),
                (obj.get("last_payment_error") or {}).get("message") if isinstance(obj.get("last_payment_error"), dict) else obj.get("last_payment_error"),
            )
            return Response({"received": True}, status=200)

        return Response({"received": True, "ignored": etype}, status=200)

    def _on_checkout_session_completed(self, event: dict) -> Response:
        obj = (event.get("data") or {}).get("object") or {}
        if (obj.get("payment_status") or "") != "paid":
            return Response({"received": True, "skipped": "not_paid"}, status=200)
        pi_id = obj.get("payment_intent") or ""
        meta = obj.get("metadata") or {}
        cref = obj.get("client_reference_id")
        raw = meta.get("order_ids") or meta.get("order_id") or cref
        if not raw:
            logger.warning("checkout.session.completed: missing order id metadata=%s", meta)
            return Response({"received": True}, status=200)
        s = str(raw).strip()
        if "," in s:
            try:
                order_ids = [int(x.strip()) for x in s.split(",") if x.strip()]
            except ValueError:
                logger.warning("checkout.session.completed: bad order ids raw=%s", raw)
                return Response({"received": True}, status=200)
        else:
            try:
                order_ids = [int(s)]
            except (TypeError, ValueError):
                logger.warning("checkout.session.completed: bad order id raw=%s", raw)
                return Response({"received": True}, status=200)
        if not pi_id:
            return Response({"received": True}, status=200)
        last_ok = None
        for order_id in order_ids:
            status, err = finalize_order_payment(order_id=order_id, payment_intent_id=str(pi_id))
            if status == "completed":
                last_ok = order_id
            elif status == "already_done":
                last_ok = order_id
            else:
                logger.error("checkout.session.completed finalize failed order=%s: %s", order_id, err)
        if last_ok is not None:
            return Response({"received": True, "order_id": last_ok, "order_ids": order_ids}, status=200)
        return Response({"received": True, "detail": "finalize_failed", "order_ids": order_ids}, status=200)

    def _on_payment_intent_succeeded(self, event: dict) -> Response:
        obj = (event.get("data") or {}).get("object") or {}
        pi_id = obj.get("id") or ""
        meta = obj.get("metadata") or {}
        order_ids_raw = meta.get("order_ids")
        order_id_raw = meta.get("order_id")

        order_ids: list[int] = []
        if order_ids_raw is not None and str(order_ids_raw).strip() != "":
            try:
                order_ids = [int(x.strip()) for x in str(order_ids_raw).split(",") if x.strip()]
            except ValueError:
                order_ids = []
        elif order_id_raw is not None and str(order_id_raw).strip() != "":
            try:
                order_ids = [int(order_id_raw)]
            except (TypeError, ValueError):
                order_ids = []

        if not order_ids and pi_id:
            order = Order.objects.filter(stripe_payment_intent_id=pi_id).first()
            if order is not None:
                order_ids = [order.id]

        if not order_ids:
            logger.warning("Stripe payment_intent.succeeded: no order for pi=%s metadata=%s", pi_id, meta)
            return Response({"received": True}, status=200)

        last_ok = None
        for oid in order_ids:
            status, err = finalize_order_payment(order_id=oid, payment_intent_id=pi_id)
            if status == "completed":
                last_ok = oid
            elif status == "already_done":
                last_ok = oid
            else:
                logger.error("Stripe payment_intent.succeeded finalize failed order=%s: %s", oid, err)
                if err and "Could not verify" in err:
                    return Response({"received": False, "detail": err}, status=500)
        if last_ok is not None:
            return Response({"received": True, "order_id": last_ok, "order_ids": order_ids}, status=200)
        return Response({"received": True, "detail": "finalize_failed", "order_ids": order_ids}, status=200)
