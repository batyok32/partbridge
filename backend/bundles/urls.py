from django.urls import path

from .views import BundleCategoryListView, BundleDetailView, BundleListView

urlpatterns = [
    path("", BundleListView.as_view(), name="bundle-list"),
    path("<int:pk>/", BundleDetailView.as_view(), name="bundle-detail"),
    path("categories/", BundleCategoryListView.as_view(), name="bundle-category-list"),
]
