from rest_framework import serializers
from zoneinfo import available_timezones
from voice_core.tenant.models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    max_users = serializers.IntegerField(default=50)
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
