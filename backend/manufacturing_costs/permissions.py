from rest_framework.permissions import BasePermission


class IsAdminOrSuperuser(BasePermission):
    """Same rule as every other app's own permissions.py — kept local rather than shared."""
    message = "Only admins or superusers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )
