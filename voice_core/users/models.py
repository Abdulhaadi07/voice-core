
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ForeignKey
from django.db.models import UUIDField
from django.db.models import DateTimeField
from django.db.models import PROTECT
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for Voice Core.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """
    tenant = ForeignKey("tenant.Tenant", on_delete=PROTECT, related_name="users")

    # First and last name do not cover name patterns around the globe
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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects: ClassVar[UserManager] = UserManager()

    def __str__(self):
        return self.email
