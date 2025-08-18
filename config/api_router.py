from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from voice_core.users.api.views import UserViewSet
from voice_core.tenant.api.views import TenantViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register(r"user", UserViewSet, basename="user")
router.register(r"tenants", TenantViewSet, basename="tenant")
# router.register(r"user-role", RoleViewSet, basename="role")

app_name = "api"
urlpatterns = router.urls
