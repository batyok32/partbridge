from django.urls import path

from .views import (
    CategoryListView,
    HomeFeaturedCategoriesView,
    HomeRecentItemsView,
    ItemDetailView,
    ItemListView,
    OptionCategoryListView,
    OptionFiltersView,
    PartNumberAutocompleteView,
    VariationListView,
)

urlpatterns = [
    path("items/", ItemListView.as_view(), name="parts-item-list"),
    path("option-filters/", OptionFiltersView.as_view(), name="parts-option-filters"),
    path("option-categories/", OptionCategoryListView.as_view(), name="parts-option-categories"),
    path("part-number-autocomplete/", PartNumberAutocompleteView.as_view(), name="parts-pn-autocomplete"),
    path("items/<int:pk>/", ItemDetailView.as_view(), name="parts-item-detail"),
    path("categories/", CategoryListView.as_view(), name="parts-category-list"),
    path("home/featured-categories/", HomeFeaturedCategoriesView.as_view(), name="parts-home-categories"),
    path("home/recent/", HomeRecentItemsView.as_view(), name="parts-home-recent"),
    path("variations/", VariationListView.as_view(), name="parts-variation-list"),
]
