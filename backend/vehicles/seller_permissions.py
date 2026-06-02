from rest_framework import permissions


class IsApprovedSeller(permissions.BasePermission):
    """Any authenticated user can list and sell parts — verification removed."""

    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
