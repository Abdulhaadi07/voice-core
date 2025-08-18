import logging
from typing import TYPE_CHECKING
from datetime import datetime
from rest_framework.exceptions import ValidationError, APIException
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.models import UserManager as DjangoUserManager

from voice_core.users.registration.cognito import create_cognito_user, delete_cognito_user
from voice_core.services.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid
from voice_core.services.wazo_helpers.wazo_user import create_wazo_user, delete_wazo_user
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.users.utils import resolve_tenant_from_email
from voice_core.custom_error_exception import raise_custom_drf_exception
from voice_core.utils.mail import send_welcome_msg
if TYPE_CHECKING:
    from .models import User  # noqa: F401

logger = logging.getLogger(__name__)


class UserManager(DjangoUserManager["User"]):
    """Custom manager for the User model."""

    def _resolve_tenant(self, email: str):
        return resolve_tenant_from_email(email)

    def _create_cognito(self, email: str, password: str | None, name: str) -> str | None:
        return create_cognito_user(email, password, name)

    def _save_user(self, email: str, password: str | None, **extra_fields):
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        user.refresh_from_db()
        return user

    def _get_wazo_admin_token(self) -> str | None:
        return get_wazo_admin_token()

    def _get_wazo_tenant_uuid(self, tenant, admin_token: str):
        return get_wazo_tenant_uuid(tenant, admin_token)

    def _assign_platform_role(self, user, group_name: str = "agent"):
        assigned_group = Group.objects.get(name=group_name)
        user.groups.add(assigned_group)
        return assigned_group

    def _determine_tenant_role(self, does_tenant_pre_exist: bool) -> str:
        return "admin" if does_tenant_pre_exist is False else "agent"

    def _provision_wazo_user(self, user, admin_token: str, tenant_uuid: str):
        return create_wazo_user(user, admin_token, tenant_uuid)

    def _update_user_with_wazo(self, user, tenant_role: str, wazo_user_id: str, wazo_username: str):
        user.tenant_role = tenant_role
        user.wazo_user_id = wazo_user_id
        user.wazo_username = wazo_username
        user.wazo_provisioned_at = datetime.now()
        user.save()
        return user

    def _send_welcome_msg(self, user):
        send_welcome_msg(user.name, user.email)

    def _perform_wazo_actions(self, email: str, cognito_sub: str | None, user, tenant):
        # Step 3.1: Get Wazo admin token
        admin_token = self._get_wazo_admin_token()
        if not admin_token:
            logger.exception("Fail to get Wazo admin token")
            self._rollback_on_failure(email, cognito_sub, user)
            raise raise_custom_drf_exception(503, "Failed to get Wazo admin token")

        logger.info("User creation step 3.1 complete: Wazo admin token obtained")

        # Step 3.2: Get tenant UUID
        tenant_uuid, does_tenant_pre_exist = self._get_wazo_tenant_uuid(tenant, admin_token)
        if not tenant_uuid:
            logger.exception("Fail to get wazo tenant UUID")
            self._rollback_on_failure(email, cognito_sub, user)
            raise raise_custom_drf_exception(503, "Failed to get Wazo tenant UUID")

        logger.info(f"User creation step 3.2 complete: tenant_uuid {tenant_uuid}")

        # Step 3.3: Assign platform role
        assigned_group_name = "agent"
        try:
            self._assign_platform_role(user, assigned_group_name)
        except Group.DoesNotExist:
            logger.exception(f"Required platform role group missing: {assigned_group_name}")
            self._rollback_on_failure(email, cognito_sub, user)
            raise raise_custom_drf_exception(503, f"Required role group '{assigned_group_name}' does not exist")

        logger.info(f"User creation step 3.3 complete: user platform role '{assigned_group_name}'")

        # Step 3.4: Determine tenant role
        assigned_tenant_role = self._determine_tenant_role(does_tenant_pre_exist)
        logger.info(
            f"User creation step 3.4 complete: user role for this tenant: '{tenant}' is '{assigned_tenant_role}'"
        )

        # Step 3.5: Create Wazo user
        wazo_user_id, wazo_username = self._provision_wazo_user(user, admin_token, tenant_uuid)
        if not wazo_user_id:
            logger.exception("Fail to create Wazo user")
            self._rollback_on_failure(email, cognito_sub, user)
            raise raise_custom_drf_exception(503, "Failed to create Wazo user")

        logger.info(f"User creation step 3.5 complete: wazo_user_id {wazo_user_id}")

        return assigned_tenant_role, wazo_user_id, wazo_username, admin_token

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError("The given email must be set")
        
        # Always resolve tenant from email
        tenant = self._resolve_tenant(email)
        extra_fields["tenant"] = tenant
        
        cognito_sub = None
        user = None

        try:
            # Step 1: Create Cognito user
            cognito_start_time = datetime.now()
            cognito_sub = self._create_cognito(email, password, extra_fields.get("name", ""))

            if not cognito_sub:
                logger.error(f"Fail to create user at cognito")
                raise raise_custom_drf_exception(503,"Failed to create Cognito user")

            logger.info(f"User creation step 1 complete: Cognito user created with sub ID {cognito_sub}")
            extra_fields["cognito_sub"] = cognito_sub
            cognito_end_time = datetime.now()

            # Step 2: Save user to Django DB
            user = self._save_user(email, password, **extra_fields)
            djangoDb_user_save_end_time = datetime.now()

            logger.info(f"User creation step 2 complete: DjangoDb user created with user ID {user.pk}")

            # Step 3: Create wazo user
            assigned_tenant_role, wazo_user_id, wazo_username, admin_token = self._perform_wazo_actions(
                email=email,
                cognito_sub=cognito_sub,
                user=user,
                tenant=tenant,
            )

            # Step 4: Update User with Wazo information
            try:
                
                self._update_user_with_wazo(user, assigned_tenant_role, wazo_user_id, wazo_username)
                
                wazo_user_create_end_time = datetime.now()
                logger.info(f"User created successfully: {email} (Cognito sub: {cognito_sub})")

                # Calculate all time diffs
                cognito_duration = (cognito_end_time - cognito_start_time).total_seconds()
                db_duration = (djangoDb_user_save_end_time - cognito_end_time).total_seconds()
                wazo_duration = (wazo_user_create_end_time - djangoDb_user_save_end_time).total_seconds()
                total_duration = (wazo_user_create_end_time - cognito_start_time).total_seconds()

                # Send welcome email asynchronously
                self._send_welcome_msg(user)

                logger.info(
                    f"User created successfully: {email} (Cognito sub: {cognito_sub}) | "
                    f"Cognito: {cognito_duration:.3f}s, "
                    f"DB Save: {db_duration:.3f}s, "
                    f"Wazo: {wazo_duration:.3f}s, "
                    f"Total: {total_duration:.3f}s"
                )
                return user
    
            except Exception as e:
                # If saving Wazo info fails, rollback everything
                logger.exception(f"Fail at saving wazo info: {wazo_user_id} {e} ")
                self._rollback_on_failure(email, cognito_sub, user, str(wazo_user_id), admin_token)
                raise raise_custom_drf_exception(503,f"Failed to save Wazo information: {str(e)}")
                
        except (ValidationError, APIException):
            raise
        except Exception as e:
            # If any other error occurs, rollback everything
            self._rollback_on_failure(email, cognito_sub, user)
            logger.exception("Failed to create user")
            raise raise_custom_drf_exception(503,f"Failed to create New user: {str(e)}")

    def _rollback_on_failure(self, email: str, cognito_sub: str | None, user=None, wazo_user_uuid: str | None = None, admin_token: str | None = None):
        """Rollback method to delete user from all systems on failure."""
        logger.info(f"Starting rollback for failed user creation: {email}")
        rollback_errors = []
        
        # Delete from Django DB if user was created
        if user and user.pk:
            try:
                user.delete()
                logger.info(f"Deleted user from Django DB: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Django DB: {email}, error: {e}"
                logger.error(error_msg)
                rollback_errors.append(error_msg)
        
        # Delete from Cognito if cognito_sub exists
        if cognito_sub:
            try:
                delete_cognito_user(email)
                logger.info(f"Deleted user from Cognito: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Cognito: {email}, error: {e}"
                logger.error(error_msg)
                rollback_errors.append(error_msg)
        
        # Delete from Wazo if wazo_user_uuid exists
        if wazo_user_uuid:
            try:
                delete_wazo_user(wazo_user_uuid, admin_token)  
                logger.info(f"Deleted user from Wazo: {email}")
            except Exception as e:
                error_msg = f"Failed to delete user from Wazo: {email}, error: {e}"
                logger.error(error_msg)
                rollback_errors.append(error_msg)
        
        # If any rollback operations failed, raise an exception
        if rollback_errors:
            logger.error(f"Rollback failed: {'; '.join(rollback_errors)}")
            raise raise_custom_drf_exception(503, f"rollback failed: {'; '.join(rollback_errors)}")

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
