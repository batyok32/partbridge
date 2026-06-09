from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
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
from .models import EmailVerificationChallenge, SellerApplication, ShippingAddress, UserCar
from .serializers import (
    EmailVerifiedTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    SellerApplicationCreateSerializer,
    ShippingAddressSerializer,
    UserCarSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .zip_lookup import lookup_us_zip_digits

User = get_user_model()


def _issue_verification(user):
    EmailVerificationChallenge.objects.filter(
        user=user, consumed_at__isnull=True
    ).update(consumed_at=timezone.now())
    challenge, code = EmailVerificationChallenge.create_for_user(user)
    from .emailing import build_email_verify_link_token

    link_token = build_email_verify_link_token(user.pk)
    name = user.get_full_name() or user.email
    send_verification_email(
        to_email=user.email,
        name=name,
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
                EmailVerificationChallenge.objects.filter(user=user, consumed_at__isnull=True)
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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_seller:
            print("Already a seller")
            return Response(
                {"detail": "You are already a seller."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.email_verified_at:
            print("Email not verified")
            return Response(
                {"detail": "Verify your email before applying to sell."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if SellerApplication.objects.filter(user=user, status=SellerApplication.Status.PENDING).exists():
            print("Pending application exists")
            return Response(
                {"detail": "You already have a pending application."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = SellerApplicationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        SellerApplication.objects.create(user=user, **ser.validated_data)
        if not user.is_seller:
            user.is_seller = True
            user.save(update_fields=["is_seller"])
        return Response(
            {
                "detail": "You are now a seller. You can list vehicles and parts. Your account is pending approval — listings will be visible to buyers once approved.",
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
        name = user.get_full_name() or user.email
        send_password_reset_email(to_email=user.email, name=name, reset_url=reset_url)
        return Response({"detail": "If an account exists, you will receive an email."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"detail": "Password updated. You can sign in."})


class UsZipLookupView(APIView):
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


class UserCarListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cars = UserCar.objects.filter(user=request.user)
        return Response(UserCarSerializer(cars, many=True).data)

    def post(self, request):
        ser = UserCarSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(UserCarSerializer(obj).data, status=status.HTTP_201_CREATED)


class UserCarDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk: int):
        car = get_object_or_404(UserCar, pk=pk, user=request.user)
        car.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SellerPublicProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk: int):
        user = get_object_or_404(User.objects.filter(pk=pk, is_seller=True))
        display_name = user.get_full_name().strip() or user.email.split("@")[0]

        from django.db.models import Avg, Count
        from orders.models import Order, OrderItem, SellerReview
        from parts.models import Item as PartItem
        from parts.serializers import ItemListSerializer
        from vehicles.models import Vehicle

        reviews_qs = SellerReview.objects.filter(seller=user)
        rating_agg = reviews_qs.aggregate(avg=Avg("rating"), count=Count("id"))
        rating_avg = round(rating_agg["avg"], 1) if rating_agg["avg"] else None
        rating_count = rating_agg["count"] or 0
        rating_breakdown = {str(r): reviews_qs.filter(rating=r).count() for r in range(1, 6)}

        completed_sales = OrderItem.objects.filter(
            item__vehicle__seller=user,
            order__status=Order.Status.DELIVERED,
        ).count()

        active_items = (
            PartItem.objects.filter(vehicle__seller=user, status=PartItem.Status.ACTIVE)
            .select_related("category", "vehicle__generation__car_model__make", "vehicle__seller")
            .prefetch_related("photos", "compatibilities")
        )[:20]
        listings_data = ItemListSerializer(active_items, many=True).data

        recent_reviews_qs = (
            reviews_qs.select_related("buyer", "order_item__item")
            .order_by("-created_at")[:15]
        )
        recent_reviews = []
        for rev in recent_reviews_qs:
            item_title = ""
            try:
                item_title = rev.order_item.item.title if rev.order_item and rev.order_item.item else ""
            except Exception:
                pass
            recent_reviews.append({
                "rating": rev.rating,
                "body": rev.body,
                "buyer_name": rev.buyer.first_name or rev.buyer.email.split("@")[0],
                "item_title": item_title,
                "created_at": rev.created_at.date().isoformat(),
            })

        vehicles_qs = (
            Vehicle.objects.filter(seller=user, status=Vehicle.Status.ACTIVE)
            .select_related("generation__car_model__make")[:10]
        )
        vehicles = []
        for v in vehicles_qs:
            make_name = ""
            model_name = ""
            gen_name = ""
            if v.generation:
                make_name = v.generation.car_model.make.name
                model_name = v.generation.car_model.name
                gen_name = v.generation.name or ""
            item_count = PartItem.objects.filter(vehicle=v, status=PartItem.Status.ACTIVE).count()
            vehicles.append({
                "id": v.id,
                "year": v.year,
                "make_name": make_name,
                "model_name": model_name,
                "generation_name": gen_name,
                "active_items_count": item_count,
            })

        return Response({
            "id": user.id,
            "display_name": display_name,
            "member_since": timezone.localtime(user.date_joined).date().isoformat(),
            "rating_avg": rating_avg,
            "rating_count": rating_count,
            "rating_breakdown": rating_breakdown,
            "completed_sales": completed_sales,
            "active_listings": listings_data,
            "recent_reviews": recent_reviews,
            "vehicles": vehicles,
        })
