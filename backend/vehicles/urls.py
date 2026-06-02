from django.urls import path

from .views import (
    VehicleDetailView,
    VehicleItemListView,
    VehicleListCreateView,
    VehiclePhotoDeleteView,
    VehiclePhotoListCreateView,
    VinDecodeView,
)

urlpatterns = [
    path("vin/decode/", VinDecodeView.as_view(), name="vin-decode"),
    path("vehicles/", VehicleListCreateView.as_view(), name="vehicle-list"),
    path("vehicles/<int:pk>/", VehicleDetailView.as_view(), name="vehicle-detail"),
    path("vehicles/<int:vehicle_id>/photos/", VehiclePhotoListCreateView.as_view(), name="vehicle-photos"),
    path("vehicles/<int:vehicle_id>/photos/<int:photo_id>/", VehiclePhotoDeleteView.as_view(), name="vehicle-photo-delete"),
    path("vehicles/<int:vehicle_id>/items/", VehicleItemListView.as_view(), name="vehicle-items"),
]
