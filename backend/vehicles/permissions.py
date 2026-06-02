from rest_framework import permissions


class IsVehicleOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return getattr(obj, "owner_id", None) == request.user.id


class IsVehiclePartOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.vehicle.owner_id == request.user.id
