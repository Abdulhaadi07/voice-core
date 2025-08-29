from datetime import datetime
from rest_framework.exceptions import ValidationError
from voice_core.tenant.models import Tenant
from voice_core.users.models import VoicemailAssignment, User
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_voicemail import update_voicemail_as_read
import logging

logger = logging.getLogger(__name__)


def set_voicemail_as_read(
    tenant: Tenant,
    user: User,
    voicemail_id: int,
    message_id: str,
    folder_id: int = 2,  # default to "Old" folder
) -> dict:
    """
    Mark a voicemail message as read by moving it to the specified folder.
    """
    try:
        # Validate tenant
        if not tenant.wazo_tenant_uuid:
            raise ValidationError("Tenant is missing wazo_tenant_uuid")

        # Validate voicemail assignment
        try:
            assignment = VoicemailAssignment.objects.get(user=user, voicemail_id=voicemail_id)
        except VoicemailAssignment.DoesNotExist:
            raise ValidationError("Voicemail not assigned to this user.")

        # Get Wazo admin token
        admin_token = get_wazo_admin_token()

        logger.info(
            f"Marking voicemail message as read | tenant_id={tenant.id}, user_id={user.id}, "
            f"voicemail_id={voicemail_id}, message_id={message_id}, folder_id={folder_id}"
        )
        start_time = datetime.now()

        # Call Wazo API to update message folder
        result = update_voicemail_as_read(
            admin_token=admin_token,
            voicemail_id=voicemail_id,
            message_id=message_id,
            folder_id=folder_id,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"Voicemail message marked as read in {duration:.3f}s | "
            f"tenant_id={tenant.id}, user_id={user.id}, voicemail_id={voicemail_id}, message_id={message_id}"
        )

        return result

    except Exception as e:
        logger.error(
            f"Error marking voicemail as read | tenant_id={tenant.id}, user_id={getattr(user, 'id', 'unknown')}, "
            f"voicemail_id={voicemail_id}, message_id={message_id}: {e}",
            exc_info=True,
        )
        raise
