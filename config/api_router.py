from django.conf import settings
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from voice_core.users.api.views.tenant_user_views import TenantUserViewSet
from voice_core.users.api.views.user_views import UserViewSet
from voice_core.tenant.api.views.tenant_views import TenantViewSet
from voice_core.tenant.api.views.extension_views import ExtensionViewSet
from voice_core.tenant.api.views.voicemail_views import VoicemailViewSet


router = DefaultRouter() if settings.DEBUG else SimpleRouter()

# users
router.register(r"users", UserViewSet, basename="user")

# tenant-management
router.register(r"tenants", TenantViewSet, basename="tenant")

# user-management (tenant-scoped users)
tenant_user_urls = [
    path(
        'tenants/<int:tenant_id>/users/',
        TenantUserViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='tenant-users-list-create'
    ),
    path(
        'tenants/<int:tenant_id>/users/<int:user_id>/',
        TenantUserViewSet.as_view({'get': 'retrieve', 'patch':'partial_update'}),
        name='tenant-users-detail-update'
    )
]

# extension-management
extension_management_urls = [
    path(
        'tenants/<int:tenant_id>/extensions/available/',
        ExtensionViewSet.as_view({'get': 'available'}),
        name="tenant-extensions-available",
    ),

    path(
        'tenants/<int:tenant_id>/users/<int:user_id>/assign/',
        ExtensionViewSet.as_view({'post': 'assign'}),
        name="tenant-extensions-assign",
    ),
]

# voicemail-management
voicemail_management_urls = [
    path(
    "tenants/<int:tenant_id>/users/<int:user_id>/voicemail/",
    VoicemailViewSet.as_view({
        "post": "set_voicemail",
        "get": "get_voicemail",
    }),
    name="tenant-voicemail",
),
]

# combine all sets; do NOT overwrite previous urlpatterns
urlpatterns = router.urls + tenant_user_urls + extension_management_urls + voicemail_management_urls