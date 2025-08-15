from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from voice_core.users.api.views import UserViewSet
from voice_core.tenant.api.views import TenantViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("user", UserViewSet)
router.register("tenants", TenantViewSet)

app_name = "api"
urlpatterns = router.urls
