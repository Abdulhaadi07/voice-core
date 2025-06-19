import logging
from typing import TYPE_CHECKING
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager as DjangoUserManager

from voice_core.users.registration.cognito import create_cognito_user
from voice_core.users.utils import resolve_tenant_from_email

if TYPE_CHECKING:
    from .models import User  # noqa: F401

logger = logging.getLogger(__name__)


class UserManager(DjangoUserManager["User"]):
    """Custom manager for the User model."""

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError("The given email must be set")
        
        # Always resolve tenant from email
        tenant = resolve_tenant_from_email(email)
        extra_fields["tenant"] = tenant

        try:
            with transaction.atomic():
                cognito_sub = create_cognito_user(email, password, extra_fields.get("name", ""))
                extra_fields["cognito_sub"] = cognito_sub

                user = self.model(email=email, **extra_fields)
                user.password = make_password(password)
                user.save(using=self._db)
                logger.info(f"User created: {email} (Cognito sub: {cognito_sub})")
                return user
        except ValidationError:
            raise
        except Exception as e:
            logger.exception("Failed to create user")
            raise ValidationError("Failed to create user. Please try again.")

    def create_user(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        return self._create_user(email, password, **extra_fields)
