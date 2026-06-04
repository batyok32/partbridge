from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from orders.models import Order, OrderItem, SellerReview

from .models import (
    EmailVerificationChallenge, SellerApplication,
    SellerVerificationDoc, ShippingAddress, User, UserCar,
)


def _is_admin_user(user):
    return user.is_superuser or user.groups.filter(name="Admin").exists()


class AdminGroupOnly:
    """Hides standalone admin from non-Admin-group staff."""
    def has_module_perms(self, request):
        return _is_admin_user(request.user)
    def has_view_permission(self, request, obj=None):
        return _is_admin_user(request.user)
    def has_add_permission(self, request):
        return _is_admin_user(request.user)
    def has_change_permission(self, request, obj=None):
        return _is_admin_user(request.user)
    def has_delete_permission(self, request, obj=None):
        return _is_admin_user(request.user)


# ── Inlines (only shown when Admin group / superuser) ─────────────────────────

class ShippingAddressInline(admin.TabularInline):
    model = ShippingAddress
    extra = 0
    fields = ("full_name", "line1", "line2", "city", "state", "zip", "is_default")


class UserCarInline(admin.TabularInline):
    model = UserCar
    extra = 0
    fields = ("generation", "modification", "year", "nickname", "is_default")
    readonly_fields = ("created_at",)


class SellerApplicationInline(admin.StackedInline):
    model = SellerApplication
    extra = 0
    fields = ("status", "bio", "rejection_reason", "submitted_at", "reviewed_at")
    readonly_fields = ("submitted_at", "reviewed_at")


class SellerVerificationDocInline(admin.TabularInline):
    model = SellerVerificationDoc
    extra = 0
    fields = ("doc_type", "file_url", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class EmailVerificationChallengeInline(admin.TabularInline):
    model = EmailVerificationChallenge
    extra = 0
    fields = ("expires_at", "consumed_at", "created_at")
    readonly_fields = ("expires_at", "consumed_at", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


class SellerReviewInline(admin.TabularInline):
    model = SellerReview
    fk_name = "seller"
    extra = 0
    fields = ("buyer", "order_item", "rating", "body", "created_at")
    readonly_fields = ("buyer", "order_item", "rating", "body", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


# ── User admin ────────────────────────────────────────────────────────────────

_ADMIN_INLINES = [
    ShippingAddressInline,
    UserCarInline,
    SellerApplicationInline,
    SellerVerificationDocInline,
    EmailVerificationChallengeInline,
    SellerReviewInline,
]


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "id", "email", "first_name", "last_name", "is_seller",
        "connect_status_display", "escrow_usd_display", "earned_usd_display",
        "email_verified_at", "is_staff", "date_joined",
    )
    list_filter = (
        "is_seller", "is_staff", "is_active",
        "stripe_connect_payouts_enabled", "stripe_connect_details_submitted",
    )
    search_fields = ("email", "first_name", "last_name", "stripe_connect_account_id")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone")}),
        (_("Permissions"), {"fields": ("is_seller", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("email_verified_at", "last_login", "date_joined")}),
        (_("Stripe Connect"), {
            "fields": (
                "stripe_connect_account_id",
                "stripe_connect_details_submitted",
                "stripe_connect_payouts_enabled",
                "stripe_connect_onboarded_at",
            ),
        }),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    readonly_fields = (
        "date_joined", "last_login",
        "stripe_connect_onboarded_at",
    )

    def get_inlines(self, request, obj):
        return _ADMIN_INLINES

    # ── Balance columns ────────────────────────────────────────────────────────

    @admin.display(description="Connect")
    def connect_status_display(self, obj):
        if not obj.stripe_connect_account_id:
            return "—"
        if obj.stripe_connect_payouts_enabled:
            return "✓ Active"
        if obj.stripe_connect_details_submitted:
            return "⏳ Pending"
        return "⚠ Incomplete"

    @admin.display(description="Escrow $")
    def escrow_usd_display(self, obj):
        if not obj.is_seller:
            return "—"
        total = OrderItem.objects.filter(
            item__vehicle__seller=obj,
            order__status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED],
        ).aggregate(s=Sum("price_at_purchase"))["s"] or 0
        return f"${total:.2f}" if total else "—"

    @admin.display(description="Earned $")
    def earned_usd_display(self, obj):
        if not obj.is_seller:
            return "—"
        total = OrderItem.objects.filter(
            item__vehicle__seller=obj,
            order__status=Order.Status.DELIVERED,
        ).aggregate(s=Sum("price_at_purchase"))["s"] or 0
        return f"${total:.2f}" if total else "—"


# ── Admin-group-only standalones ──────────────────────────────────────────────

@admin.register(ShippingAddress)
class ShippingAddressAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "city", "state", "zip", "is_default")
    list_filter = ("is_default",)
    search_fields = ("full_name", "city", "zip")


@admin.register(SellerApplication)
class SellerApplicationAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "user", "status", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__email",)


@admin.register(SellerVerificationDoc)
class SellerVerificationDocAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "user", "doc_type", "uploaded_at")
    list_filter = ("doc_type",)


@admin.register(UserCar)
class UserCarAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "user", "generation", "modification", "year", "is_default", "created_at")
    list_filter = ("is_default",)


@admin.register(EmailVerificationChallenge)
class EmailVerificationChallengeAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "user", "expires_at", "consumed_at", "created_at")
    list_filter = ("consumed_at",)
