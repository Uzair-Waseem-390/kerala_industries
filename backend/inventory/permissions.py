from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrSuperuserOrReadOnly(BasePermission):
    """
    Read access for all authenticated users.
    Write access only for admins and superusers.
    Used exclusively for Inventory — normal users can view stock levels.
    """
    message = "Only admins or superusers can modify this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff
