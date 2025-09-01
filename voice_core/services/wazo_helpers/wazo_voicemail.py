from django.core import serializers
import requests
from typing import Tuple
from config.settings.base import WAZO_API_URL
from voice_core.services.wazo_helpers.wazo_context import create_context

import logging
logger = logging.getLogger(__name__)

def _truncate(text: str, limit: int = 500) -> str:
    if text is None:
        return ""
    return text if len(text) <= limit else text[:limit] + "..."


def _headers(admin_token: str, tenant_uuid: str | None = None) -> dict:
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
    }
    if tenant_uuid:
        headers["Wazo-Tenant"] = str(tenant_uuid)
    return headers


def fetch_all_voicemail(admin_token: str, voicemail_id: int
) -> dict | None:
    """
    Fetch all recordings for a given voicemail ID.
    """
    url = f"{WAZO_API_URL}/api/calld/1.0/voicemails/{voicemail_id}"
    headers = _headers(admin_token)

    try:
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(
            f"Failed to fetch voicemail recordings (voicemail_id={voicemail_id}): {e}, "
            f"response={_truncate(getattr(e.response, 'text', ''))}"
        )
        return None


def fetch_voicemails_by_folder(admin_token: str, voicemail_id: int, folder_id: int
) -> dict | None:
    """
    Fetch voicemail recordings from a specific folder (e.g., inbox, old, deleted).
    """
    url = f"{WAZO_API_URL}/api/calld/1.0/voicemails/{voicemail_id}/folders/{folder_id}"
    headers = _headers(admin_token)

    try:
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(
            f"Failed to fetch voicemail folder recordings "
            f"(voicemail_id={voicemail_id}, folder_id={folder_id}): {e}, "
            f"response={_truncate(getattr(e.response, 'text', ''))}"
        )
        return None


def update_voicemail_as_read(
    admin_token: str, voicemail_id: int, message_id: str, folder_id: int
) -> dict | None:
    """
    Move a voicemail message into a different folder (e.g., mark as read by moving to 'Old').
    """
    url = f"{WAZO_API_URL}/api/calld/1.0/voicemails/{voicemail_id}/messages/{message_id}"
    headers = _headers(admin_token)
    data = {"folder_id": folder_id}

    try:
        resp = requests.put(url, headers=headers, json=data, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json() if resp.text else {}
    except requests.RequestException as e:
        logger.error(
            f"Failed to mark voicemail message as read "
            f"(voicemail_id={voicemail_id}, message_id={message_id}, folder_id={folder_id}): {e}, "
            f"response={_truncate(getattr(e.response, 'text', ''))}"
        )
        return None




def fetch_voicemail_recording(
    admin_token: str, voicemail_id: int, message_id: str
) -> Tuple[bytes, str] | None:
    """
    Fetch a voicemail message recording (audio/wav).
    Returns a tuple: (binary_content, content_type)
    """
    url = f"{WAZO_API_URL}/api/calld/1.0/voicemails/{voicemail_id}/messages/{message_id}/recording"
    headers = {
        "accept": "audio/wav",
        "X-Auth-Token": admin_token,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20, stream=True, verify=False)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "audio/wav")
        return resp.content, content_type
    except requests.RequestException as e:
        logger.error(
            f"Failed to fetch voicemail recording "
            f"(voicemail_id={voicemail_id}, message_id={message_id}): {e}, "
            f"response={_truncate(getattr(e.response, 'text', ''))}"
        )
        return None, None
