from datetime import datetime
from rest_framework.exceptions import ValidationError

from voice_core.tenant.models import Tenant
from voice_core.users.models import (
	ExtensionAssignment, 
	VoicemailAssignment,
	User,
)
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_extensions import (
	create_user_voicemail,
	deassociate_user_with_voicemail,
	delete_voicemail,
)

import logging
logger = logging.getLogger(__name__)


def _rollback_voicemail_assignment(
	user: User,
	admin_token: str | None,
	tenant_uuid: str | None,
	*,
	user_uuid: str | None,
	voicemail_id: int | None,
) -> None:
	"""
	Best-effort Rollback of created/linked Wazo resources using helper functions.
	This function never raises; it logs any errors encountered during Rollback.
	"""
	if not admin_token or not tenant_uuid or not voicemail_id or not user_uuid:
		return

	logger.info(
		f"Voicemail assignment rollback starts tenant_uuid={tenant_uuid}, user_uuid={user_uuid}, voicemail_id={voicemail_id}"
	)

	try:
		if voicemail_id and user_uuid:
			ok_to_deassociate_voicemail = deassociate_user_with_voicemail(admin_token, tenant_uuid, user_uuid)

			if ok_to_deassociate_voicemail:
				ok = delete_voicemail(admin_token, tenant_uuid, voicemail_id)
				if ok:
					logger.info(f"Rollback: Successfully deleted voicemail voicemail_id={voicemail_id}")
				else:
					logger.error(f"Rollback: Failed to delete voicemail voicemail_id={voicemail_id}")

				logger.info(f"Rollback: Successfully deassociated user from voicemail user_uuid={user_uuid}")
			else:
				logger.error(f"Rollback: Failed to deassociate user from voicemail user_uuid={user_uuid}")
	except Exception as exc:
		logger.error(f"Rollback: Exception while deleting voicemail error={exc}", exc_info=True)

	try:
		if voicemail_id and user:
			VoicemailAssignment.objects.filter(
				user=user,
				voicemail_id=voicemail_id
			).delete()
	except Exception as exc:
		logger.error(f"Rollback: Failed to delete VoicemailAssignment error={exc}", exc_info=True)

	try:
		# Reset user.config flags
		if user:
			user.config.extension_enabled = False
			user.config.voicemail_enabled = False
			user.config.save()
	except Exception as exc:
		logger.error(f"Rollback: Failed to reset user.config flags error={exc}", exc_info=True)

	logger.info("Rollback: Local DB rollback completed.")


def assign_voicemail(
    tenant: Tenant,
    user: User,
    voicemail_pin: int ,
    voicemail_max_messages: int
    ):
    """
    Provision resources in Wazo for a user and persist an ExtensionAssignment.
    """
    # Track created resources for Rollback
    user_uuid = None
    admin_token = None
    tenant_uuid = None
    voicemail_id = None

    try:
        admin_token = get_wazo_admin_token()
        if not tenant.wazo_tenant_uuid:
            raise ValueError("Tenant is missing wazo_tenant_uuid")
        tenant_uuid = str(tenant.wazo_tenant_uuid)

        create_user_voicemail_start_time = datetime.now()
        # Check if user has an extension assigned
        try:
            user_extension = ExtensionAssignment.objects.get(user=user)
        except ExtensionAssignment.DoesNotExist:
            raise ValidationError("User does not have an extension assigned.")

        # Check if user already has a voicemail assigned
        if VoicemailAssignment.objects.filter(user=user).exists():
            raise ValidationError("User already has a voicemail assigned.")

        # Create voicemail
        voicemail_id, voicemail_pin, enabled_flag = create_user_voicemail(
                wazo_user_id=str(user.wazo_user_id),
                tenant_uuid=tenant_uuid,
                admin_token=admin_token,
                context_name=user_extension.context_name,
                email=user.email,
                extension_number=str(user_extension.extension),
                pin=voicemail_pin,
                name=user.name,
                max_messages = voicemail_max_messages if voicemail_max_messages is not None else 10,
            )
        create_user_voicemail_end_time = datetime.now()

        # Persist voicemail assignment
        if enabled_flag:
            user.config.voicemail_enabled = True
            user.config.save()

            assignment = VoicemailAssignment.objects.create(
                voicemail_id=voicemail_id,
                voicemail_pin=voicemail_pin,
                user=user,
            )
        save_assignment_end_time = datetime.now()

        logger.info(
            f"Voicemail assigned | tenant_id={tenant.id} user_id={user.id} | voicemail_id={voicemail_id}'"
        )

        # Step durations
        voicemail_creation_time = (create_user_voicemail_end_time - create_user_voicemail_start_time).total_seconds()
        save_assignment_time = (save_assignment_end_time - create_user_voicemail_end_time).total_seconds()

        # Total duration
        total_time = (save_assignment_end_time - create_user_voicemail_start_time).total_seconds()

        logger.info(
            f"Voicemail assignment completed successfully. "
            f"Voicemail Creation: {voicemail_creation_time:.3f}s, "
            f"Save to Db: {save_assignment_time:.3f}s, "
            f"Total: {total_time:.3f}s"
        )
        if enabled_flag:
            return assignment
        return None

    except Exception as e:
        logger.error(
            f"Error assigning Voicemail for tenant_id={tenant.id} user_id={getattr(user, 'id', 'unknown')}: {e}",
            exc_info=True,
        )
        # Attempt best-effort Rollback
        try:
            _rollback_voicemail_assignment(
                user = user,
                admin_token=admin_token,
                tenant_uuid=tenant_uuid,
                user_uuid=user_uuid,
                voicemail_id=voicemail_id,
            )
        except Exception as Rollback_exc:
            logger.error(f"Rollback encountered an error: {Rollback_exc}", exc_info=True)
        raise
