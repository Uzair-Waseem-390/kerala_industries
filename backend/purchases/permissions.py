from rest_framework.permissions import BasePermission


class IsAdminOrSuperuser(BasePermission):
    """
    Full access for admins (is_staff=True) and superusers.
    Used for all purchase order writes, confirmations, returns, payments.
    Normal users have zero access to purchases.
    """
    message = "Only admins or superusers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


# IsAdminOrSuperuserOrReadOnly moved to inventory/permissions.py — it was
# used exclusively for the Inventory views, which moved with it.