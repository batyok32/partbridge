from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BrowseErrorReportView,
    CompatibleVehiclesSearchView,
    DecodeVinView,
    NormalizePartNameView,
    PartCategoryListView,
    PartFamilyListView,
    PartOptionSetView,
    PublicBrowseVehicleDetailView,
    PublicCarAssistView,
    PublicCarOptionsView,
    PublicPartBrowseView,
    PublicPartDetailView,
    PublicReverseZipView,
    TriggerPartPipelineView,
    VehiclePartDetailView,
    VehiclePartListView,
    VehiclePartBulkDeleteView,
    VehiclePartBulkUpdateView,
    VehiclePhotoDeleteView,
    VehiclePartPhotoUploadView,
    VehicleViewSet,
)

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")

urlpatterns = [
    path("vin/decode/", DecodeVinView.as_view(), name="vin-decode"),
    path("browse/cars/options/", PublicCarOptionsView.as_view(), name="browse-car-options"),
    path("browse/reverse-zip/", PublicReverseZipView.as_view(), name="browse-reverse-zip"),
    path("browse/cars/assist/", PublicCarAssistView.as_view(), name="browse-cars-assist"),
    path("browse/vehicles/<int:pk>/", PublicBrowseVehicleDetailView.as_view(), name="browse-vehicle-detail"),
    path("browse/parts/<int:pk>/", PublicPartDetailView.as_view(), name="browse-part-detail"),
    path("browse/parts/compatible/", CompatibleVehiclesSearchView.as_view(), name="browse-parts-compatible"),
    path("browse/parts/", PublicPartBrowseView.as_view(), name="browse-parts"),
    path("browse/normalize-part/", NormalizePartNameView.as_view(), name="browse-normalize-part"),
    path("browse/error-report/", BrowseErrorReportView.as_view(), name="browse-error-report"),
    path("", include(router.urls)),
    path(
        "vehicles/<int:vehicle_id>/photos/<int:photo_id>/",
        VehiclePhotoDeleteView.as_view(),
        name="vehicle-photo-delete",
    ),
    path(
        "vehicles/<int:vehicle_id>/parts/<int:part_id>/upload_photo/",
        VehiclePartPhotoUploadView.as_view(),
        name="vehicle-part-photo-upload",
    ),
    path(
        "vehicles/<int:vehicle_id>/parts/<int:part_id>/pipeline/",
        TriggerPartPipelineView.as_view(),
        name="vehicle-part-pipeline",
    ),
    path(
        "browse/parts/<int:vehicle_part_id>/options/",
        PartOptionSetView.as_view(),
        name="browse-part-options",
    ),
    path("vehicles/<int:vehicle_id>/parts/", VehiclePartListView.as_view(), name="vehicle-parts-list"),
    path(
        "vehicles/<int:vehicle_id>/parts/bulk_delete/",
        VehiclePartBulkDeleteView.as_view(),
        name="vehicle-parts-bulk-delete",
    ),
    path(
        "vehicles/<int:vehicle_id>/parts/bulk_update/",
        VehiclePartBulkUpdateView.as_view(),
        name="vehicle-parts-bulk-update",
    ),
    path(
        "vehicles/<int:vehicle_id>/parts/<int:pk>/",
        VehiclePartDetailView.as_view(),
        name="vehicle-parts-detail",
    ),
    path("catalog/part-categories/", PartCategoryListView.as_view(), name="catalog-categories"),
    path("catalog/part-families/", PartFamilyListView.as_view(), name="catalog-families"),
]
