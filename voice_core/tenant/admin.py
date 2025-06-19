from django.contrib import admin

from voice_core.tenant.models import Tenant

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "created")
    search_fields = ("name", "domain")
    ordering = ("name",)