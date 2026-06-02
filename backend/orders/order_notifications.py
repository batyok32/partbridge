from __future__ import annotations

import logging
from collections import defaultdict

from django.conf import settings

from .notifications import send_order_email

logger = logging.getLogger(__name__)


def send_order_placed_notifications(orders: list) -> None:
    """Buyer + seller(s) when order rows are created (awaiting payment)."""
    if not orders:
        return
    buyer = orders[0].buyer
    buyer_lines = [f"  • Order #{o.id} — {o.vehicle_part.label} — ${o.amount_usd}" for o in orders]
    send_order_email(
        to_email=buyer.email,
        subject=f"Order placed — {len(orders)} item(s) — Partbridge",
        body=(
            "Thank you — your order(s) are recorded.\n\n"
            + "\n".join(buyer_lines)
            + "\n\nComplete payment (from your Purchases page) to move the seller forward.\n"
        ),
    )
    by_seller: dict[int, list] = defaultdict(list)
    for o in orders:
        by_seller[o.seller_id].append(o)
    for _sid, os in by_seller.items():
        seller = os[0].seller
        lines = [f"  • Order #{o.id} — {o.vehicle_part.label} — ${o.amount_usd}" for o in os]
        send_order_email(
            to_email=seller.email,
            subject=f"New buyer order — {len(os)} line(s) — Partbridge",
            body=(
                f"Buyer {buyer.email} placed:\n\n"
                + "\n".join(lines)
                + "\n\nYou will be notified again when payment clears.\n"
            ),
        )


def send_shipping_needed_notification(order) -> None:
    """Admin notification that a new order needs a shipping label."""
    admin = (getattr(settings, "ORDER_ADMIN_EMAIL", "") or "").strip()
    if not admin:
        return
    v = order.vehicle_snapshot or {}
    veh = f"{v.get('year') or ''} {v.get('make') or ''} {v.get('model') or ''}".strip()
    send_order_email(
        to_email=admin,
        subject=f"[Admin] Shipping needed — order #{order.id}",
        body=(
            f"Order #{order.id} is ready for shipping.\n"
            f"Part: {order.vehicle_part.label}\n"
            f"Vehicle: {veh}\n"
            f"Buyer: {order.buyer.email}\n"
            f"Seller: {order.seller.email}\n"
            "Please generate a label and upload to Django admin."
        ),
    )


def send_seller_verification_submitted_email(sv) -> None:
    """Notify admin when a seller uploads identity documents."""
    admin = (getattr(settings, "ORDER_ADMIN_EMAIL", "") or "").strip()
    if not admin:
        logger.warning("ORDER_ADMIN_EMAIL not set; verification submit email skipped.")
        return
    u = sv.user
    send_order_email(
        to_email=admin,
        subject=f"[Admin] Seller verification documents submitted — {u.email}",
        body=(
            f"User: {u.email} ({u.name})\n"
            f"SellerVerification id: {sv.pk}\n"
            "Review documents in Django admin → Seller verifications.\n"
        ),
    )


def send_seller_verification_approved_email(sv) -> None:
    send_order_email(
        to_email=sv.user.email,
        subject="Your seller verification was approved — Partbridge",
        body=(
            "Your identity documents were approved. You can request payouts when your Stripe Connect "
            "balance is available (see Money & cashout).\n"
        ),
    )


def send_buyer_order_inquiry_email(*, order, topic: str, message: str, phone: str = "") -> None:
    admin = (getattr(settings, "ORDER_ADMIN_EMAIL", "") or "").strip()
    if not admin:
        logger.warning("ORDER_ADMIN_EMAIL not set; buyer inquiry not emailed to admin.")
        return
    buyer = order.buyer
    lines = [
        f"Topic: {topic}",
        f"Order #{order.id}",
        f"Buyer: {buyer.email}",
        f"Phone: {(phone or '').strip() or '—'}",
        "",
        "Message:",
        message.strip(),
        "",
        f"Part: {order.vehicle_part.label}",
        f"Order state: {order.state}",
    ]
    send_order_email(
        to_email=admin,
        subject=f"[Admin] Buyer request — {topic} — order #{order.id}",
        body="\n".join(lines),
    )


def send_delivery_photos_to_buyer(order) -> None:
    """After admin marks delivered with photos."""
    if not order.delivery_photos:
        return
    lines = "\n".join(f"  • {u}" for u in order.delivery_photos[:20])
    notes = (order.delivery_notes or "").strip()
    send_order_email(
        to_email=order.buyer.email,
        subject=f"Delivered — order #{order.id} — Partbridge",
        body=(
            "Your order is marked delivered.\n\n"
            f"Photos:\n{lines}\n"
            + (f"\nNote from team:\n{notes}\n" if notes else "")
        ),
    )
