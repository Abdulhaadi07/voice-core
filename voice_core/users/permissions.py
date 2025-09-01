from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

import logging
logger = logging.getLogger(__name__)


class IsPlatformAdminOrTenantAdmin(BasePermission):
    """
    Checks:
    1. User is authenticated
    2. Platform admin can access all tenants
    3. Tenant admin can access their own tenant
    4. Role in auth_group determines allowed actions
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"Permission denied: User not authenticated")
            return False
        
        logger.info(f"User {request.user} is requesting {view.action} on Tenant")

        # Platform admin or superuser = full access
        if request.user.is_superuser or "admin" in request.user.groups.values_list("name", flat=True):
            logger.info(f"User '{request.user}' has platform admin access")
            return True

        # For tenant-scoped views, validate tenant
        tenant_id = view.kwargs.get("tenant_id")
        if tenant_id and str(request.user.tenant_id) != str(tenant_id):
            logger.warning(f"User '{request.user}': not authenticated")
            raise PermissionDenied(f"Permission denied: User not authenticated")

        if getattr(request.user, "tenant_role", None) == "admin":
            logger.info(f"Permission denied: User not authenticated")
            return True
        logger.warning(f"Permission denied: User not authenticated")
        raise PermissionDenied(f"Permission denied: User not authenticated")
