import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def build_email_verify_link_token(user_id: int) -> str:
    return signing.dumps({"uid": user_id}, salt="lookmypart.email-verify")


def parse_email_verify_link_token(token: str, max_age: int = 72 * 3600) -> int:
    data = signing.loads(token, salt="lookmypart.email-verify", max_age=max_age)
    return int(data["uid"])


def send_verification_email(*, to_email: str, name: str, code: str, link_token: str) -> None:
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={link_token}"
    subject = "Verify your Lookmypart email"
    body = (
        f"Hi {name},\n\n"
        f"Your verification code is: {code}\n\n"
        f"Or open this link in the browser where you signed up:\n{verify_url}\n\n"
        "If you did not create an account, you can ignore this message.\n"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    except Exception as exc:
        logger.warning("send_verification_email failed for %s: %s", to_email, exc)


def send_password_reset_email(*, to_email: str, name: str, reset_url: str) -> None:
    subject = "Reset your Lookmypart password"
    body = (
        f"Hi {name},\n\n"
        f"Use this link to set a new password (valid for a limited time):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    except Exception as exc:
        logger.warning("send_password_reset_email failed for %s: %s", to_email, exc)
