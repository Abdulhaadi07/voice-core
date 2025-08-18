from django.conf import settings
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from voice_core.tenant.api.views import TenantViewSet
from voice_core.users.api.views.tenant_user_views import TenantUserViewSet
from voice_core.users.api.views.user_views import UserViewSet


router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register(r"user", UserViewSet, basename="user")

# tenant-management
router.register(r"tenants", TenantViewSet, basename="tenant")

# user-management
tenant_user_urls = [
    path(
        'tenants/<int:tenant_id>/users/',
        TenantUserViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='tenant-users-list-create'
    ),
    path(
        'tenants/<int:tenant_id>/users/<int:pk>/',
        TenantUserViewSet.as_view({'get': 'retrieve', 'patch':'partial_update'}),
        name='tenant-users-detail-update'
    )
]

urlpatterns = router.urls + tenant_user_urls