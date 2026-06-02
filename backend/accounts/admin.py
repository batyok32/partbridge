from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import EmailVerificationChallenge, SellerApplication, ShippingAddress, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "name", "phone", "role", "email_verified_at", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_superuser", "email_verified_at")
    search_fields = ("email", "name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal"), {"fields": ("name", "phone", "role")}),
        (_("Verification"), {"fields": ("email_verified_at",)}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "phone", "role", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("date_joined", "last_login")


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "label", "city", "state", "postal_code", "is_default", "updated_at")
    list_filter = ("state", "is_default")
    search_fields = ("user__email", "line1", "city", "postal_code")
    raw_id_fields = ("user",)


@admin.register(EmailVerificationChallenge)
class EmailVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "consumed_at", "created_at")
    list_filter = ("consumed_at",)
    search_fields = ("user__email",)
    readonly_fields = ("code_digest", "created_at")


@admin.register(SellerApplication)
class SellerApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "business_name",
        "status",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status",)
    search_fields = ("user__email", "business_name", "why_sell")
    readonly_fields = ("created_at", "updated_at", "reviewed_at", "reviewed_by")
    raw_id_fields = ("user", "reviewed_by")
    actions = ("approve_applications", "reject_applications")

    @admin.action(description="Approve — grant seller access (buy + sell)")
    def approve_applications(self, request, queryset):
        pending = queryset.filter(status=SellerApplication.Status.PENDING)
        count = 0
        for app in pending.select_related("user"):
            u = app.user
            u.role = User.Role.BOTH
            u.save(update_fields=["role"])
            app.status = SellerApplication.Status.APPROVED
            app.reviewed_at = timezone.now()
            app.reviewed_by = request.user
            app.save(
                update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"]
            )
            count += 1
        self.message_user(request, f"Approved {count} application(s).")

    @admin.action(description="Reject selected (set staff rejection reason in form first)")
    def reject_applications(self, request, queryset):
        pending = queryset.filter(status=SellerApplication.Status.PENDING)
        count = pending.update(
            status=SellerApplication.Status.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"Rejected {count} application(s). Add rejection text via edit if needed.")
