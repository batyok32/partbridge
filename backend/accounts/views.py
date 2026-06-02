from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .emailing import (
    parse_email_verify_link_token,
    send_password_reset_email,
    send_verification_email,
)
from .models import EmailVerificationChallenge, SellerApplication, ShippingAddress

from orders.models import SellerReview
from vehicles.models import VehiclePart
from .zip_lookup import lookup_us_zip_digits
from .serializers import (
    EmailVerifiedTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    SellerApplicationCreateSerializer,
    ShippingAddressSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)

User = get_user_model()


def _issue_verification(user):
    EmailVerificationChallenge.objects.filter(
        user=user, consumed_at__isnull=True
    ).update(consumed_at=timezone.now())
    challenge, code = EmailVerificationChallenge.create_for_user(user)
    from .emailing import build_email_verify_link_token

    link_token = build_email_verify_link_token(user.pk)
    send_verification_email(
        to_email=user.email,
        name=user.name,
        code=code,
        link_token=link_token,
    )
    return challenge


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        _issue_verification(user)
        return Response(
            {
                "detail": "Account created. Check your email for a verification code and link.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifyEmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data.get("token")
        if token:
            try:
                uid = parse_email_verify_link_token(token)
            except signing.BadSignature:
                return Response({"detail": "Invalid or expired link."}, status=400)
            except signing.SignatureExpired:
                return Response({"detail": "Verification link expired."}, status=400)
            try:
                user = User.objects.get(pk=uid)
            except User.DoesNotExist:
                return Response({"detail": "Invalid link."}, status=400)
        else:
            email = ser.validated_data["email"].lower().strip()
            code = ser.validated_data["code"]
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"detail": "Invalid code or email."}, status=400)
            if user.email_verified_at:
                return Response({"detail": "Email already verified."})
            challenge = (
                EmailVerificationChallenge.objects.filter(
                    user=user, consumed_at__isnull=True
                )
                .order_by("-created_at")
                .first()
            )
            if not challenge or not challenge.is_valid():
                return Response({"detail": "Code expired. Request a new one."}, status=400)
            from django.contrib.auth.hashers import check_password

            if not check_password(code, challenge.code_digest):
                return Response({"detail": "Invalid code or email."}, status=400)
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["consumed_at"])

        if user.email_verified_at:
            return Response({"detail": "Email already verified.", "user": UserSerializer(user).data})
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        return Response({"detail": "Email verified.", "user": UserSerializer(user).data})


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = ResendVerificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If an account exists, a new code was sent."})
        if user.email_verified_at:
            return Response({"detail": "Email already verified."})
        _issue_verification(user)
        return Response({"detail": "If an account exists, a new code was sent."})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SellerApplicationView(APIView):
    """Submit a request to become an approved seller (reviewed in Django admin)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role in (User.Role.SELLER, User.Role.BOTH):
            return Response(
                {"detail": "You are already an approved seller."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.email_verified_at:
            return Response(
                {"detail": "Verify your email before applying to sell."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if SellerApplication.objects.filter(
            user=user, status=SellerApplication.Status.PENDING
        ).exists():
            return Response(
                {"detail": "You already have a pending application."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = SellerApplicationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        SellerApplication.objects.create(user=user, **ser.validated_data)
        return Response(
            {
                "detail": "Application submitted. We will email you when it is reviewed.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailVerifiedTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If an account exists, you will receive an email."})
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        tok = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={tok}"
        send_password_reset_email(to_email=user.email, name=user.name, reset_url=reset_url)
        return Response({"detail": "If an account exists, you will receive an email."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"detail": "Password updated. You can sign in."})


class UsZipLookupView(APIView):
    """Authenticated lookup: US ZIP → city, state (for checkout forms)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (request.query_params.get("zip") or "").strip()
        if not qs:
            return Response({"detail": "Provide a zip query parameter."}, status=status.HTTP_400_BAD_REQUEST)
        result = lookup_us_zip_digits(qs)
        if not result:
            return Response({"detail": "ZIP not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


class ShippingAddressListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ShippingAddress.objects.filter(user=request.user)
        return Response(ShippingAddressSerializer(qs, many=True).data)

    def post(self, request):
        ser = ShippingAddressSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(ShippingAddressSerializer(obj, context={"request": request}).data, status=status.HTTP_201_CREATED)


class SellerPublicProfileView(APIView):
    """Public seller card for buyers (no email/phone)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, pk: int):
        user = get_object_or_404(
            User.objects.filter(pk=pk, role__in=(User.Role.SELLER, User.Role.BOTH))
        )
        display_name = (user.name or "").strip() or (user.email or "").split("@")[0]
        reviews = SellerReview.objects.filter(seller_id=user.id)
        agg = reviews.aggregate(avg=Avg("rating"), c=Count("id"))
        avg = agg["avg"]
        part_qs = VehiclePart.objects.filter(vehicle__owner_id=user.id, is_removed=False)
        return Response(
            {
                "id": user.id,
                "display_name": display_name,
                "completed_sales": part_qs.filter(
                    listing_state=VehiclePart.ListingState.SOLD
                ).count(),
                "rating_avg": round(float(avg), 2) if avg is not None else None,
                "rating_count": int(agg["c"] or 0),
                "active_buy_now_listings": part_qs.filter(
                    listing_state=VehiclePart.ListingState.BUY_NOW
                ).count(),
                "member_since": timezone.localtime(user.date_joined).date().isoformat(),
            }
        )


class ShippingAddressDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk: int):
        addr = get_object_or_404(ShippingAddress, pk=pk, user=request.user)
        ser = ShippingAddressSerializer(addr, data=request.data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(ShippingAddressSerializer(obj, context={"request": request}).data)

    def delete(self, request, pk: int):
        addr = get_object_or_404(ShippingAddress, pk=pk, user=request.user)
        addr.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
