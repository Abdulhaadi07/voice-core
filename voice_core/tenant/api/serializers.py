from rest_framework import serializers
from voice_core.tenant.models import Tenant
from voice_core.users.models import User


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "domain",
            "max_users",
            "status",
            "wazo_tenant_uuid",
        ]
        read_only_fields = ["id", "wazo_tenant_uuid"]
