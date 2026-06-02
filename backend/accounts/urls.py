from django.urls import path

from . import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/verify-email", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-verification", views.ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh", views.RefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    path("auth/seller-application", views.SellerApplicationView.as_view(), name="auth-seller-application"),
    path("auth/password-reset", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password-reset/confirm", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("us-zip-lookup/", views.UsZipLookupView.as_view(), name="us-zip-lookup"),
    path("shipping-addresses/", views.ShippingAddressListView.as_view(), name="shipping-addresses"),
    path("shipping-addresses/<int:pk>/", views.ShippingAddressDetailView.as_view(), name="shipping-address-detail"),
    path("sellers/<int:pk>/public/", views.SellerPublicProfileView.as_view(), name="seller-public-profile"),
    path("user-cars/", views.UserCarListView.as_view(), name="user-cars"),
    path("user-cars/<int:pk>/", views.UserCarDetailView.as_view(), name="user-car-detail"),
]
