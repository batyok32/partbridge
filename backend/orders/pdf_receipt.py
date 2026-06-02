"""Generate a simple order receipt PDF (buyer/seller)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import Order


def build_order_receipt_pdf(order: Order, *, role: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    y = h - 50
    snap = order.vehicle_snapshot if isinstance(order.vehicle_snapshot, dict) else {}
    lines = [
        "Partbridge — Order receipt",
        "",
        f"Order #{order.id}",
        f"Role: {role}",
        f"State: {order.state}",
        "",
        f"Part: {order.vehicle_part.label}",
        f"Vehicle: {snap.get('year') or ''} {snap.get('make') or ''} {snap.get('model') or ''}".strip(),
        f"VIN: {snap.get('vin') or '—'}",
        "",
        f"Buyer paid (total): ${order.amount_usd}",
        f"Shipping line: ${order.shipping_amount_usd}",
        f"Shipping mode: {order.shipping_mode or '—'}",
        "",
        f"Buyer: {order.buyer.email}",
        f"Seller: {order.seller.email}",
        "",
        f"Created: {order.created_at}",
        f"Paid: {order.paid_at or '—'}",
        f"Delivered: {order.delivered_at or '—'}",
    ]
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(50, y, str(line)[:100])
        y -= 16
        if y < 60:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 11)
    c.save()
    return buf.getvalue()
