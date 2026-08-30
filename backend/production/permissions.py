from rest_framework.permissions import BasePermission


class IsAdminOrSuperuser(BasePermission):
    """
    Full access for admins (is_staff=True) and superusers. Normal users have
    zero access to the production app. Mirrors purchases.permissions
    (each app keeps its own copy rather than sharing one).
    """
    message = "Only admins or superusers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )
