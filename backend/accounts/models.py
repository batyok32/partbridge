import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address must be set.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32)

    class Role(models.TextChoices):
        BUYER = "buyer", "Buyer"
        SELLER = "seller", "Seller"
        BOTH = "both", "Buyer and seller"

    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.BUYER,
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone"]

    objects = UserManager()

    def __str__(self):
        return self.email


class ShippingAddress(models.Model):
    """Buyer saved shipping destinations (ZIP + state drive rate quotes)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shipping_addresses",
    )
    label = models.CharField(max_length=64, default="Home")
    recipient_name = models.CharField(max_length=128, blank=True)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=16)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at", "-id"]

    def __str__(self):
        return f"{self.user_id} · {self.label} ({self.city}, {self.state})"


class SellerApplication(models.Model):
    """Request to upgrade from buyer to approved seller (staff reviews in admin)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="seller_applications",
    )
    business_name = models.CharField(max_length=200, blank=True)
    why_sell = models.TextField(max_length=4000)
    inventory_summary = models.TextField(max_length=4000)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seller_applications_reviewed",
    )
    staff_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.status}"


class EmailVerificationChallenge(models.Model):
    """Stores a short-lived hashed code sent by email (and complements magic-link token)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_challenges",
    )
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_for_user(cls, user, *, ttl_minutes: int = 60) -> tuple["EmailVerificationChallenge", str]:
        from django.contrib.auth.hashers import make_password

        code = f"{secrets.randbelow(1_000_000):06d}"
        digest = make_password(code, salt="email-verify")
        challenge = cls.objects.create(
            user=user,
            code_digest=digest,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return challenge, code

    def is_valid(self) -> bool:
        if self.consumed_at is not None:
            return False
        return timezone.now() <= self.expires_at
