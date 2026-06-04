from django.urls import path

from .views import BundleCategoryListView, BundleDetailView, BundleListView, BundleSearchView

urlpatterns = [
    path("", BundleListView.as_view(), name="bundle-list"),
    path("search/", BundleSearchView.as_view(), name="bundle-search"),
    path("<int:pk>/", BundleDetailView.as_view(), name="bundle-detail"),
    path("categories/", BundleCategoryListView.as_view(), name="bundle-category-list"),
]
