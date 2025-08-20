
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ForeignKey
from django.db.models import UUIDField
from django.db.models import DateTimeField
from django.db.models import PROTECT
from django.utils.translation import gettext_lazy as _
from django.db import models
from .managers import UserManager
from django_extensions.db.models import TimeStampedModel
from django.conf import settings
from cryptography.fernet import Fernet

from config.settings.base import SIP_ENCRYPTION_KEY

class User(AbstractUser):
    """
    Default custom user model for Voice Core.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """
    tenant = ForeignKey("tenant.Tenant", on_delete=PROTECT, related_name="users")

    name = CharField(_("Name of User"), blank=True, max_length=255)
    email = EmailField(_("email address"), unique=True)
    cognito_sub = CharField(_("Cognito User ID"), max_length=128, unique=True)

    # Wazo-related fields
    wazo_user_id = UUIDField(_("Wazo User ID"), blank=True, null=True)
    wazo_username = CharField(_("Wazo Username"), max_length=255, blank=True, null=True)
    wazo_provisioned_at = DateTimeField(_("Wazo Provisioned At"), blank=True, null=True)


    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    username = None  # type: ignore[assignment]

    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    AGENT = "agent"

    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (SUPERVISOR, "Supervisor"),
        (AGENT, "Agent"),
    ]
    tenant_role = CharField(max_length=20, choices=ROLE_CHOICES, default=AGENT)  


    ACTIVE = "active"
    INACTIVE = "inactive"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
    ]
    status = CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)  

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects: ClassVar[UserManager] = UserManager()

    def __str__(self):
        return self.email

fernet = Fernet(settings.SIP_ENCRYPTION_KEY)

class EncryptedCharField(models.CharField):
    """CharField that encrypts on save and decrypts on read."""

    def get_prep_value(self, value):
        """Encrypt before saving to DB"""
        if value is None:
            return value
        return fernet.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from DB"""
        if value is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value
            
class ExtensionAssignment(TimeStampedModel):
    """Represents the assignment of a SIP extension to a user."""

    extension = models.CharField(max_length=20)   
    sip_username = EncryptedCharField(max_length=128)
    sip_password = EncryptedCharField(max_length=128)          
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="extensions"
    )
    wazo_line_id = models.IntegerField()  
    context_name = models.CharField(max_length=250) 

    voicemail_id = models.IntegerField(null=True,blank=True)
    voicemail_pin = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Numeric PIN for accessing voicemail"
    )
    voicemail_enabled = models.BooleanField(
        default=True,
        help_text="Enable or disable voicemail for this extension"
    )

    class Meta:
        verbose_name = "Extension Assignment"
        verbose_name_plural = "Extension Assignments"

    def __str__(self):
        return f"{self.extension} ({self.user.email})"