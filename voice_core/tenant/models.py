from django.db import models
from django_extensions.db.models import TimeStampedModel

class Tenant(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    domain = models.CharField(max_length=255, unique=True, blank=True, null=True)

    # Wazo-related fields
    wazo_tenant_uuid = models.UUIDField(unique=True, blank=True, null=True)

    def __str__(self):
        return self.name