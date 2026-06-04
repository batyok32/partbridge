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
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_seller = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    stripe_connect_account_id = models.CharField(max_length=64, blank=True)
    stripe_connect_details_submitted = models.BooleanField(default=False)
    stripe_connect_payouts_enabled = models.BooleanField(default=False)
    stripe_connect_onboarded_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class ShippingAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shipping_addresses",
    )
    full_name = models.CharField(max_length=128)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=16)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-id"]

    def __str__(self):
        return f"{self.user_id} — {self.full_name} ({self.city}, {self.state})"


class SellerApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_applications",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    bio = models.TextField()
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.user.email} — {self.status}"


class SellerVerificationDoc(models.Model):
    class DocType(models.TextChoices):
        GOV_ID = "gov_id", "Government ID"
        BUSINESS_LICENSE = "business_license", "Business License"
        DEALER_LICENSE = "dealer_license", "Dealer License"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_docs",
    )
    doc_type = models.CharField(max_length=24, choices=DocType.choices)
    file_url = models.CharField(max_length=1024)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SellerVerificationDoc user={self.user_id} type={self.doc_type}"


class UserCar(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_cars",
    )
    generation = models.ForeignKey(
        "catalog.Generation",
        on_delete=models.CASCADE,
        related_name="user_cars",
    )
    modification = models.ForeignKey(
        "catalog.Modification",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="user_cars",
    )
    year = models.PositiveSmallIntegerField()
    nickname = models.CharField(max_length=128, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"UserCar user={self.user_id} gen={self.generation_id} year={self.year}"


class EmailVerificationChallenge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
