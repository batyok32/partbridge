from django.urls import path

from .views import (
    CartItemDeleteView,
    CartView,
    DisputeDetailView,
    DisputeListCreateView,
    DisputeMessageCreateView,
    OrderDetailView,
    OrderListView,
    PurchasesListView,
    SellerReviewCreateView,
)

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/<int:item_id>/", CartItemDeleteView.as_view(), name="cart-item-delete"),
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/purchases/", PurchasesListView.as_view(), name="purchases"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("disputes/", DisputeListCreateView.as_view(), name="dispute-list"),
    path("disputes/order-item/<int:order_item_id>/", DisputeListCreateView.as_view(), name="dispute-create"),
    path("disputes/<int:pk>/", DisputeDetailView.as_view(), name="dispute-detail"),
    path("disputes/<int:dispute_id>/messages/", DisputeMessageCreateView.as_view(), name="dispute-messages"),
    path("order-items/<int:order_item_id>/review/", SellerReviewCreateView.as_view(), name="order-item-review"),
]
