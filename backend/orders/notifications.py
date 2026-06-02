from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_order_email(*, to_email: str, subject: str, body: str) -> None:
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    except Exception as exc:
        logger.warning("send_order_email failed to=%s: %s", to_email, exc)


def send_order_sms(*, to_phone: str, message: str) -> None:
    # MVP stub hook for Phase 8. Replace with Twilio/etc in production.
    logger.info("sms_stub to=%s message=%s", to_phone, message)
