# tenants/views.py
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from voice_core.tenant.models import Tenant
from .serializers import TenantSerializer

from rest_framework import mixins, viewsets, status
from rest_framework.response import Response

class TenantViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):  
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser] #only Admin access to tenant

    def partial_update(self, request, *args, **kwargs):
        tenant = self.get_object()
        serializer = self.get_serializer(tenant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
