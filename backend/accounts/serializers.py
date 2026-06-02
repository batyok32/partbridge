from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import SellerApplication, ShippingAddress, UserCar

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    is_approved_seller = serializers.SerializerMethodField()
    seller_application = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_seller",
            "is_approved_seller",
            "seller_application",
            "email_verified_at",
            "date_joined",
        )
        read_only_fields = fields

    def get_is_approved_seller(self, obj):
        return obj.is_seller

    def get_seller_application(self, obj):
        app = SellerApplication.objects.filter(user=obj).order_by("-submitted_at").first()
        if not app:
            return None
        out = {"id": app.id, "status": app.status, "submitted_at": app.submitted_at}
        if app.status == SellerApplication.Status.REJECTED and app.rejection_reason:
            out["rejection_reason"] = app.rejection_reason
        return out


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("email", "password", "first_name", "last_name", "phone")

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class SellerApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerApplication
        fields = ("bio",)

    def validate_bio(self, value):
        t = (value or "").strip()
        if len(t) < 20:
            raise serializers.ValidationError("Please write at least a few sentences.")
        return t


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    code = serializers.CharField(required=False, max_length=6, min_length=6)
    token = serializers.CharField(required=False, allow_blank=False, max_length=4096)

    def validate(self, attrs):
        if not attrs.get("token") and not (attrs.get("email") and attrs.get("code")):
            raise serializers.ValidationError("Provide either token or email and code.")
        if attrs.get("token") and (attrs.get("email") or attrs.get("code")):
            raise serializers.ValidationError("Send only token, or email and code — not both.")
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerifiedTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.email_verified_at:
            raise AuthenticationFailed(
                detail={
                    "detail": "Email address is not verified.",
                    "code": "email_not_verified",
                }
            )
        data["user"] = UserSerializer(self.user).data
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        try:
            uid = urlsafe_base64_decode(attrs["uid"]).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, UnicodeDecodeError):
            raise serializers.ValidationError({"uid": "Invalid user."})
        token = attrs["token"]
        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError({"token": "Invalid or expired token."})
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = ("id", "full_name", "line1", "line2", "city", "state", "zip", "is_default", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_state(self, value):
        s = (value or "").strip().upper()[:2]
        if len(s) != 2:
            raise serializers.ValidationError("Use a 2-letter state code.")
        return s

    def create(self, validated_data):
        user = self.context["request"].user
        if validated_data.get("is_default"):
            ShippingAddress.objects.filter(user=user).update(is_default=False)
        return ShippingAddress.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("is_default"):
            ShippingAddress.objects.filter(user=instance.user).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)


class UserCarSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCar
        fields = ("id", "user", "generation", "modification", "year", "nickname", "is_default", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def create(self, validated_data):
        user = self.context["request"].user
        if validated_data.get("is_default"):
            UserCar.objects.filter(user=user).update(is_default=False)
        return UserCar.objects.create(user=user, **validated_data)
