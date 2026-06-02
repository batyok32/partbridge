import re
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from accounts.emailing import build_email_verify_link_token
from accounts.models import EmailVerificationChallenge, SellerApplication, User


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _register(self, email="buyer@example.com", **kwargs):
        payload = {
            "email": email,
            "password": "strong-pass-1",
            "name": "Test User",
            "phone": "+12065550199",
            **kwargs,
        }
        r = self.client.post("/api/v1/auth/register", payload, format="json")
        return r, payload

    def _code_from_outbox(self):
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        m = re.search(r"code is:\s*(\d{6})", body)
        self.assertIsNotNone(m, msg=body)
        return m.group(1)

    def test_register_sends_email_and_creates_user(self):
        mail.outbox.clear()
        r, payload = self._register()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(email=payload["email"])
        self.assertIsNone(user.email_verified_at)
        self.assertTrue(
            EmailVerificationChallenge.objects.filter(user=user, consumed_at__isnull=True).exists()
        )
        self.assertEqual(user.role, User.Role.BUYER)

    def test_register_always_buyer_even_if_role_sent(self):
        mail.outbox.clear()
        r, payload = self._register(
            email="rolehack@example.com",
            role="both",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=payload["email"])
        self.assertEqual(user.role, User.Role.BUYER)

    def test_login_blocked_until_verified(self):
        mail.outbox.clear()
        r, payload = self._register(email="unverified@example.com")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post(
            "/api/v1/auth/login",
            {"email": payload["email"], "password": payload["password"]},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(r2.json().get("code"), "email_not_verified")

    def test_verify_with_code_then_login_and_me(self):
        mail.outbox.clear()
        r, payload = self._register(email="verified@example.com")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        code = self._code_from_outbox()

        r_v = self.client.post(
            "/api/v1/auth/verify-email",
            {"email": payload["email"], "code": code},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK, msg=r_v.json())
        self.assertIn("user", r_v.json())

        r_login = self.client.post(
            "/api/v1/auth/login",
            {"email": payload["email"], "password": payload["password"]},
            format="json",
        )
        self.assertEqual(r_login.status_code, status.HTTP_200_OK, msg=r_login.json())
        data = r_login.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertIn("user", data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        r_me = self.client.get("/api/v1/auth/me")
        self.assertEqual(r_me.status_code, status.HTTP_200_OK)
        self.assertEqual(r_me.json()["email"], payload["email"])

    def test_verify_with_magic_link_token(self):
        mail.outbox.clear()
        r, payload = self._register(email="magic@example.com")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=payload["email"])
        token = build_email_verify_link_token(user.pk)

        r_v = self.client.post(
            "/api/v1/auth/verify-email",
            {"token": token},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)

    def test_me_requires_authentication(self):
        self.client.credentials()
        r = self.client.get("/api/v1/auth/me")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        mail.outbox.clear()
        _, payload = self._register(email="refresh@example.com")
        code = self._code_from_outbox()
        self.client.post(
            "/api/v1/auth/verify-email",
            {"email": payload["email"], "code": code},
            format="json",
        )
        r_login = self.client.post(
            "/api/v1/auth/login",
            {"email": payload["email"], "password": payload["password"]},
            format="json",
        )
        refresh = r_login.json()["refresh"]
        r_ref = self.client.post(
            "/api/v1/auth/token/refresh",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(r_ref.status_code, status.HTTP_200_OK, msg=r_ref.json())
        self.assertIn("access", r_ref.json())

    def test_resend_verification(self):
        mail.outbox.clear()
        _, payload = self._register(email="resend@example.com")
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox.clear()
        r = self.client.post(
            "/api/v1/auth/resend-verification",
            {"email": payload["email"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_verification_survives_email_provider_failure(self):
        _, payload = self._register(email="resend-fail@example.com")
        with patch("accounts.emailing.send_mail", side_effect=ConnectionRefusedError("smtp down")):
            r = self.client.post(
                "/api/v1/auth/resend-verification",
                {"email": payload["email"]},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm(self):
        mail.outbox.clear()
        _, payload = self._register(email="reset@example.com")
        code = self._code_from_outbox()
        self.client.post(
            "/api/v1/auth/verify-email",
            {"email": payload["email"], "code": code},
            format="json",
        )
        user = User.objects.get(email=payload["email"])

        mail.outbox.clear()
        r_req = self.client.post(
            "/api/v1/auth/password-reset",
            {"email": payload["email"]},
            format="json",
        )
        self.assertEqual(r_req.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        r_conf = self.client.post(
            "/api/v1/auth/password-reset/confirm",
            {"uid": uid, "token": token, "new_password": "new-strong-9"},
            format="json",
        )
        self.assertEqual(r_conf.status_code, status.HTTP_200_OK, msg=r_conf.json())

        user.refresh_from_db()
        self.assertTrue(check_password("new-strong-9", user.password))

        r_old = self.client.post(
            "/api/v1/auth/login",
            {"email": payload["email"], "password": payload["password"]},
            format="json",
        )
        self.assertEqual(r_old.status_code, status.HTTP_401_UNAUTHORIZED)

        r_new = self.client.post(
            "/api/v1/auth/login",
            {"email": payload["email"], "password": "new-strong-9"},
            format="json",
        )
        self.assertEqual(r_new.status_code, status.HTTP_200_OK)

    def test_seller_application_requires_verified_email(self):
        mail.outbox.clear()
        _, payload = self._register(email="apply-unver@example.com")
        self.assertEqual(len(mail.outbox), 1)
        user = User.objects.get(email=payload["email"])
        self.client.force_authenticate(user=user)
        r = self.client.post(
            "/api/v1/auth/seller-application",
            {
                "why_sell": "I run a small yard and want to list donor vehicles.",
                "inventory_summary": "Mostly late-model Honda and Toyota.",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_application_submitted_when_verified(self):
        mail.outbox.clear()
        _, payload = self._register(email="apply-ver@example.com")
        code = self._code_from_outbox()
        self.client.post(
            "/api/v1/auth/verify-email",
            {"email": payload["email"], "code": code},
            format="json",
        )
        user = User.objects.get(email=payload["email"])
        self.client.force_authenticate(user=user)
        r = self.client.post(
            "/api/v1/auth/seller-application",
            {
                "business_name": "Test Yard",
                "why_sell": "I run a small yard and want to list donor vehicles here.",
                "inventory_summary": "Mostly late-model Honda and Toyota.",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, msg=r.json())
        self.assertTrue(
            SellerApplication.objects.filter(
                user=user, status=SellerApplication.Status.PENDING
            ).exists()
        )
        r2 = self.client.post(
            "/api/v1/auth/seller-application",
            {
                "why_sell": "Second application should not be allowed while pending.",
                "inventory_summary": "More inventory text here.",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
