from datetime import datetime
from rest_framework.exceptions import ValidationError
from voice_core.users.models import (
	VoicemailAssignment,
)
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_voicemail import (
	fetch_all_voicemail,
	fetch_voicemails_by_folder,
    fetch_voicemail_recording,
)

import logging
logger = logging.getLogger(__name__)


def get_all_voicemails(
    tenant,
    user,
    voicemail_id: int,
):
    """
    Fetch all voicemail recordings for a user from Wazo and return metadata.
    """

    admin_token = None
    tenant_uuid = None

    try:
        # Ensure tenant has Wazo tenant UUID
        if not tenant.wazo_tenant_uuid:
            raise ValidationError("Tenant is missing wazo_tenant_uuid")
        tenant_uuid = str(tenant.wazo_tenant_uuid)

        # Ensure user has a voicemail assigned
        try:
            assignment = VoicemailAssignment.objects.get(user=user, voicemail_id=voicemail_id)
        except VoicemailAssignment.DoesNotExist:
            raise ValidationError("Voicemail not assigned to this user.")

        admin_token = get_wazo_admin_token()

        logger.info(
            f"Fetching voicemail recordings | tenant_id={tenant.id}, user_id={user.id}, voicemail_id={voicemail_id}"
        )
        start_time = datetime.now()

        # Call Wazo API to fetch voicemail recordings
        all_voicemails = fetch_all_voicemail(
            voicemail_id=voicemail_id,
            admin_token=admin_token,
        )

        if all_voicemails is None:
            return None

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(
            f"Fetched {len(all_voicemails)} voicemail recordings in {duration:.3f}s "
            f"| tenant_id={tenant.id}, user_id={user.id}, voicemail_id={voicemail_id}"
        )

        return all_voicemails

    except Exception as e:
        logger.error(
            f"Error fetching voicemail recordings | tenant_id={tenant.id}, user_id={getattr(user, 'id', 'unknown')}, voicemail_id={voicemail_id}: {e}",
            exc_info=True,
        )
        raise

def get_voicemails_by_folder(
    tenant,
    user,
    voicemail_id: int,
    folder_id: int,
):
    """
    Fetch voicemail recordings for a user from a specific folder (e.g., Inbox, Old, Deleted).
    """
    admin_token = None
    tenant_uuid = None

    try:
        if not tenant.wazo_tenant_uuid:
            raise ValidationError("Tenant is missing wazo_tenant_uuid")
        tenant_uuid = str(tenant.wazo_tenant_uuid)

        try:
            assignment = VoicemailAssignment.objects.get(user=user, voicemail_id=voicemail_id)
        except VoicemailAssignment.DoesNotExist:
            raise ValidationError("Voicemail not assigned to this user.")

        admin_token = get_wazo_admin_token()

        logger.info(
            f"Fetching voicemail recordings by folder | tenant_id={tenant.id}, user_id={user.id}, "
            f"voicemail_id={voicemail_id}, folder_id={folder_id}"
        )
        start_time = datetime.now()

        recordings = fetch_voicemails_by_folder(
            voicemail_id=voicemail_id,
            folder_id=folder_id,
            admin_token=admin_token,
        )

        if recordings is None:
            return None

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(
            f"Fetched {len(recordings)} recordings from folder {folder_id} in {duration:.3f}s "
            f"| tenant_id={tenant.id}, user_id={user.id}, voicemail_id={voicemail_id}"
        )

        return recordings

    except Exception as e:
        logger.error(
            f"Error fetching voicemail recordings by folder | tenant_id={tenant.id}, "
            f"user_id={getattr(user, 'id', 'unknown')}, voicemail_id={voicemail_id}, folder_id={folder_id}: {e}",
            exc_info=True,
        )
        raise


def get_voicemail_recording(
    tenant,
    user,
    voicemail_id: int,
    message_id: str,
):
    """
    Return (chunk_iterator, headers) for proxy streaming.
    """
    try:
        if not getattr(tenant, "wazo_tenant_uuid", None):
            raise ValidationError("Tenant is missing wazo_tenant_uuid")

        # Validate ownership/assignment
        assignment = VoicemailAssignment.objects.filter(user=user, voicemail_id=voicemail_id).first()
        if not assignment:
            raise ValidationError("Voicemail not assigned to this user.")

        admin_token = get_wazo_admin_token()

        chunks_iter, headers = fetch_voicemail_recording(
            admin_token=admin_token,
            voicemail_id=voicemail_id,
            message_id=message_id,
        )
        return chunks_iter, headers
    except Exception as e:
        logger.error(
            f"Error fetching voicemail recording | tenant_id={getattr(tenant, 'id', 'unknown')}, "
            f"user_id={getattr(user, 'id', 'unknown')}, voicemail_id={voicemail_id}, message_id={message_id}: {e}",
            exc_info=True,
        )
        raise 