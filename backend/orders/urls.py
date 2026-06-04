from django.urls import path

from .stripe_webhook import StripeWebhookView
from .views import (
    AddBundleToCartView,
    BuyerConfirmDeliveryView,
    CartBundleDeleteView,
    CartCheckoutView,
    CartItemDeleteView,
    CartPreviewCheckoutView,
    CartView,
    DisputeDetailView,
    DisputeListCreateView,
    DisputeMessageCreateView,
    OrderDetailView,
    OrderListView,
    PaymentVerifyView,
    PurchasesListView,
    SellerActionQueueView,
    SellerCashoutView,
    SellerConnectOnboardView,
    SellerConnectRefreshView,
    SellerMoneySummaryView,
    SellerReviewCreateView,
    SellerOrderDetailView,
    SellerSalesListView,
    SellerShippingPlanView,
    SellerVerificationView,
)

urlpatterns = [
    # Cart
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/<int:item_id>/", CartItemDeleteView.as_view(), name="cart-item-delete"),
    path("cart/bundle/<int:bundle_id>/", AddBundleToCartView.as_view(), name="cart-bundle-add"),
    path("cart/bundle/<int:bundle_id>/remove/", CartBundleDeleteView.as_view(), name="cart-bundle-delete"),
    path("cart/preview-checkout/", CartPreviewCheckoutView.as_view(), name="cart-preview-checkout"),
    path("cart/checkout/", CartCheckoutView.as_view(), name="cart-checkout"),
    path("cart/verify-payment/", PaymentVerifyView.as_view(), name="cart-verify-payment"),

    # Stripe webhook (no auth — verified via Stripe-Signature header)
    path("orders/payments/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),

    # Orders (buyer)
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/purchases/", PurchasesListView.as_view(), name="purchases"),

    # Seller — static paths must come before <int:pk> routes
    path("orders/sales/", SellerSalesListView.as_view(), name="seller-sales"),
    path("orders/sales/<int:pk>/", SellerOrderDetailView.as_view(), name="seller-sale-detail"),
    path("orders/seller/action-queue/", SellerActionQueueView.as_view(), name="seller-action-queue"),
    path("orders/money/summary/", SellerMoneySummaryView.as_view(), name="seller-money-summary"),
    path("orders/money/cashout/", SellerCashoutView.as_view(), name="seller-cashout"),
    path("orders/connect/onboard/", SellerConnectOnboardView.as_view(), name="seller-connect-onboard"),
    path("orders/connect/refresh/", SellerConnectRefreshView.as_view(), name="seller-connect-refresh"),
    path("orders/seller-verification/", SellerVerificationView.as_view(), name="seller-verification"),

    # Parameterised order routes
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/confirm-delivery/", BuyerConfirmDeliveryView.as_view(), name="order-confirm-delivery"),
    path("orders/<int:pk>/shipping-plan/suggest/", SellerShippingPlanView.as_view(), name="seller-shipping-plan-suggest"),
    path("orders/<int:pk>/shipping-plan/", SellerShippingPlanView.as_view(), name="seller-shipping-plan"),

    # Disputes
    path("disputes/", DisputeListCreateView.as_view(), name="dispute-list"),
    path("disputes/order-item/<int:order_item_id>/", DisputeListCreateView.as_view(), name="dispute-create"),
    path("disputes/<int:pk>/", DisputeDetailView.as_view(), name="dispute-detail"),
    path("disputes/<int:dispute_id>/messages/", DisputeMessageCreateView.as_view(), name="dispute-messages"),

    # Reviews
    path("order-items/<int:order_item_id>/review/", SellerReviewCreateView.as_view(), name="order-item-review"),
]
