from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import EmailVerificationChallenge, SellerApplication, SellerVerificationDoc, ShippingAddress, User, UserCar


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("id", "email", "first_name", "last_name", "is_seller", "email_verified_at", "is_staff", "date_joined")
    list_filter = ("is_seller", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone")}),
        (_("Permissions"), {"fields": ("is_seller", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("email_verified_at", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    readonly_fields = ("date_joined", "last_login")


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "city", "state", "zip", "is_default")
    list_filter = ("is_default",)
    search_fields = ("full_name", "city", "zip")


@admin.register(SellerApplication)
class SellerApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("user__email",)


@admin.register(SellerVerificationDoc)
class SellerVerificationDocAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "doc_type", "uploaded_at")
    list_filter = ("doc_type",)


@admin.register(UserCar)
class UserCarAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "generation", "modification", "year", "is_default", "created_at")
    list_filter = ("is_default",)


@admin.register(EmailVerificationChallenge)
class EmailVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "expires_at", "consumed_at", "created_at")
    list_filter = ("consumed_at",)
