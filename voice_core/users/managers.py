import logging
from typing import TYPE_CHECKING
from datetime import datetime
from rest_framework.exceptions import ValidationError, APIException
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager as DjangoUserManager

from voice_core.users.registration.cognito import create_cognito_user, delete_cognito_user
from voice_core.users.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid
from voice_core.users.wazo_helpers.wazo_user import create_wazo_user, delete_wazo_user
from voice_core.users.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.users.utils import resolve_tenant_from_email
from voice_core.custom_error_exception import raise_custom_drf_exception

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
        
        cognito_sub = None
        user = None
        
        try:
            # Step 1: Create Cognito user
            cognito_sub = create_cognito_user(email, password, extra_fields.get("name", ""))
            if not cognito_sub:
                logger.error(f"Fail to create user at cognito")
                raise raise_custom_drf_exception(503,"Failed to create Cognito user")
            
            extra_fields["cognito_sub"] = cognito_sub
            
            # Step 2: Save user to Django DB
            user = self.model(email=email, **extra_fields)
            user.password = make_password(password)
            user.save(using=self._db)
            user.refresh_from_db()

            # Step 3: Get Wazo admin token
            admin_token = get_wazo_admin_token()
            if not admin_token:
                # If admin token fails, delete user from DB and Cognito
                logger.exception(f"Fail to get Wazo admin token")
                self._cleanup_on_failure(email, cognito_sub, user)
                raise raise_custom_drf_exception(503,"Failed to get Wazo admin token")
            
            # Step 4: Get tenant UUID
            tenant_uuid = get_wazo_tenant_uuid(tenant, admin_token)
            if not tenant_uuid:
                # If tenant UUID fails, delete user from DB and Cognito
                logger.exception(f"Fail to get wazo tenant UUID")
                self._cleanup_on_failure(email, cognito_sub, user)
                raise raise_custom_drf_exception(503,"Failed to get Wazo tenant UUID")
            
            # Step 5: Create Wazo user
            [wazo_user_id, wazo_username] = create_wazo_user(user, admin_token, tenant_uuid)
            if not wazo_user_id:
                # If Wazo user creation fails, delete user from DB and Cognito
                logger.exception(f"Fail to create Wazo user")
                self._cleanup_on_failure(email, cognito_sub, user)
                raise raise_custom_drf_exception(503,"Failed to create Wazo user")
            
            # Step 6: Save all Wazo information
            try:
                user.wazo_user_id = wazo_user_id
                user.wazo_username = wazo_username
                user.wazo_provisioned_at = datetime.now()
                user.save()
                
                logger.info(f"User created successfully: {email} (Cognito sub: {cognito_sub})")
                return user
    
            except Exception as e:
                # If saving Wazo info fails, cleanup everything
                logger.exception(f"Fail at saving wazo info: {wazo_user_id} {e} ")
                self._cleanup_on_failure(email, cognito_sub, user, str(wazo_user_id), admin_token)
                raise raise_custom_drf_exception(503,f"Failed to save Wazo information: {str(e)}")
                
        except (ValidationError, APIException):
            raise
        except Exception as e:
            # If any other error occurs, cleanup everything
            self._cleanup_on_failure(email, cognito_sub, user)
            logger.exception("Failed to create user")
            raise raise_custom_drf_exception(503,f"Failed to create user: {str(e)}")

    def _cleanup_on_failure(self, email: str, cognito_sub: str | None, user=None, wazo_user_uuid: str | None = None, admin_token: str | None = None):
        """Cleanup method to delete user from all systems on failure."""
        logger.info(f"Starting cleanup for failed user creation: {email}")
        cleanup_errors = []
        
        # Delete from Django DB if user was created
        if user and user.pk:
            try:
                user.delete()
                logger.info(f"Deleted user from Django DB: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Django DB: {email}, error: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # Delete from Cognito if cognito_sub exists
        if cognito_sub:
            try:
                delete_cognito_user(email)
                logger.info(f"Deleted user from Cognito: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Cognito: {email}, error: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # Delete from Wazo if wazo_user_uuid exists
        if wazo_user_uuid:
            try:
                delete_wazo_user(wazo_user_uuid, admin_token)  
                logger.info(f"Deleted user from Wazo: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Wazo: {email}, error: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # If any cleanup operations failed, raise an exception
        if cleanup_errors:
            logger.error(f"Fail to clean up")
            raise raise_custom_drf_exception(503, f"Cleanup failed: {'; '.join(cleanup_errors)}")

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
