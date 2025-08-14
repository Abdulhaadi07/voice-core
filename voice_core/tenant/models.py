from django.db import models
from django_extensions.db.models import TimeStampedModel

class Tenant(TimeStampedModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    name = models.CharField(max_length=255, unique=True)
    domain = models.CharField(max_length=255, unique=True, blank=True, null=True)
    
    max_users = models.IntegerField(default=50)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    # Wazo-related fields
    wazo_tenant_uuid = models.UUIDField(unique=True, blank=True, null=True)

    def __str__(self):
        return self.name