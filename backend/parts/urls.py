from django.urls import path

from .views import CategoryListView, ItemDetailView, ItemListView, VariationListView

urlpatterns = [
    path("items/", ItemListView.as_view(), name="parts-item-list"),
    path("items/<int:pk>/", ItemDetailView.as_view(), name="parts-item-detail"),
    path("categories/", CategoryListView.as_view(), name="parts-category-list"),
    path("variations/", VariationListView.as_view(), name="parts-variation-list"),
]
