from django.urls import path

from .views import CarModelListView, GenerationListView, MakeListView, ModificationListView

urlpatterns = [
    path("makes/", MakeListView.as_view(), name="catalog-makes"),
    path("models/", CarModelListView.as_view(), name="catalog-models"),
    path("generations/", GenerationListView.as_view(), name="catalog-generations"),
    path("modifications/", ModificationListView.as_view(), name="catalog-modifications"),
]
