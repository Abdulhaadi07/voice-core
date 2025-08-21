import requests
import time
from typing import Tuple
from config.settings.base import WAZO_API_URL

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


def create_line(admin_token: str, tenant_uuid: str, context_name: str) -> Tuple[int, str]:
    """
    Create a line in Wazo for a context. Returns (line_id, provisioning_code).
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines"
    data = {
        "context": context_name,
    }
    start = time.perf_counter()
    logger.info(f"create_line_start tenant_uuid={tenant_uuid} context={context_name} url={url}")
    try:
        resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"create_line_request_error tenant_uuid={tenant_uuid} context={context_name} error={exc} duration_ms={duration_ms}")
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 201):
        payload = resp.json()
        line_id = int(payload.get("id"))
        provisioning_extension = payload.get("provisioning_extension", "")
        logger.info(f"create_line_success tenant_uuid={tenant_uuid} context={context_name} line_id={line_id} provisioning_extension={provisioning_extension} duration_ms={duration_ms}")
        return line_id, provisioning_extension
    logger.error(f"create_line_failed tenant_uuid={tenant_uuid} context={context_name} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    resp.raise_for_status()


def create_extension(admin_token: str, tenant_uuid: str, context_name: str, exten: int) -> int:
    """
    Create an extension in a context. Returns extension id.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/extensions"
    data = {
        "context": context_name,
        "exten": str(exten),
    }
    start = time.perf_counter()
    logger.info(f"create_extension_start tenant_uuid={tenant_uuid} context={context_name} exten={exten} url={url}")
    try:
        resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"create_extension_request_error tenant_uuid={tenant_uuid} context={context_name} exten={exten} error={exc} duration_ms={duration_ms}")
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 201):
        payload = resp.json()
        extension_id = int(payload.get("id"))
        logger.info(f"create_extension_success tenant_uuid={tenant_uuid} context={context_name} exten={exten} extension_id={extension_id} duration_ms={duration_ms}")
        return extension_id
    logger.error(f"create_extension_failed tenant_uuid={tenant_uuid} context={context_name} exten={exten} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    resp.raise_for_status()


def create_sip_endpoint(
    admin_token: str,
    tenant_uuid: str,
    username: str,
    password: str,
    label: str,
) -> Tuple[str, str, str]:
    """
    Create a SIP endpoint. Returns (uuid, label).
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip"
    transport_udp_uuid = get_transport_uuid(admin_token)
    global_template_uuid = get_global_template_uuid(admin_token, tenant_uuid)
    logger.info(f"create_sip_endpoint_dependencies transport_udp_uuid={transport_udp_uuid} global_template_uuid={global_template_uuid}")
    data = {
        "auth_section_options": [["username", username], ["password", password]],
        "endpoint_section_options": [["rewrite_contact", "yes"], ["force_rport", "yes"],["rtp_symmetric", "yes"]],
        "label": label,
        "name": username,
        "templates": [{"uuid": global_template_uuid}],
        "transport": {"uuid": transport_udp_uuid}
    }
    start = time.perf_counter()
    logger.info(f"create_sip_endpoint_start tenant_uuid={tenant_uuid} label={label} url={url}")
    try:
        resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"create_sip_endpoint_request_error tenant_uuid={tenant_uuid} label={label} error={exc} duration_ms={duration_ms}")
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 201):
        payload = resp.json()
        endpoint_uuid = payload.get("uuid")
        endpoint_label = payload.get("label")
        endpoint_name = payload.get("name")
        logger.info(f"create_sip_endpoint_success tenant_uuid={tenant_uuid} uuid={endpoint_uuid} label={endpoint_label} name={endpoint_name} duration_ms={duration_ms}")
        return endpoint_uuid, endpoint_label, endpoint_name
    logger.error(f"create_sip_endpoint_failed tenant_uuid={tenant_uuid} label={label} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    resp.raise_for_status()


def assign_line_with_sip_endpoint(admin_token: str, tenant_uuid: str, line_id: int, sip_uuid: str) -> bool:
    """
    Attach a SIP endpoint to a line. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/endpoints/sip/{sip_uuid}"
    start = time.perf_counter()
    logger.info(f"assign_line_with_sip_endpoint_start tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} url={url}")
    try:
        resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"assign_line_with_sip_endpoint_request_error tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"assign_line_with_sip_endpoint_success tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} duration_ms={duration_ms}")
        return True
    logger.error(f"assign_line_with_sip_endpoint_failed tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def assign_line_with_extension(admin_token: str, tenant_uuid: str, line_id: int, extension_id: int) -> bool:
    """
    Attach a line to an extension. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/extensions/{extension_id}"
    start = time.perf_counter()
    logger.info(f"assign_line_with_extension_start tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} url={url}")
    try:
        resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"assign_line_with_extension_request_error tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"assign_line_with_extension_success tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} duration_ms={duration_ms}")
        return True
    logger.error(f"assign_line_with_extension_failed tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def assign_user_with_line(admin_token: str, tenant_uuid: str, user_uuid: str, line_id: int) -> bool:
    """
    Attach a line to a user. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_uuid}/lines/{line_id}"
    start = time.perf_counter()
    logger.info(f"assign_user_with_line_start tenant_uuid={tenant_uuid} user_uuid={user_uuid} line_id={line_id} url={url}")
    try:
        resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"assign_user_with_line_request_error tenant_uuid={tenant_uuid} user_uuid={user_uuid} line_id={line_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"assign_user_with_line_success tenant_uuid={tenant_uuid} user_uuid={user_uuid} line_id={line_id} duration_ms={duration_ms}")
        return True
    logger.error(f"assign_user_with_line_failed tenant_uuid={tenant_uuid} user_uuid={user_uuid} line_id={line_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def get_transport_uuid(admin_token: str):
    url = f"{WAZO_API_URL}/api/confd/1.1/sip/transports"
    start = time.perf_counter()
    logger.info(f"get_transport_uuid_start url={url}")
    try:
        resp = requests.get(url, headers=_headers(admin_token), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"get_transport_uuid_request_error error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 200:
        payload = resp.json()
        transport_udp_obj = next(
            (item for item in payload.get("items", []) if item.get("name") == "transport-udp"),
            None,
        )
        if not transport_udp_obj:
            logger.error(f"get_transport_uuid_not_found duration_ms={duration_ms}")
            return False
        udp_uuid = transport_udp_obj.get("uuid")
        logger.info(f"get_transport_uuid_success uuid={udp_uuid} duration_ms={duration_ms}")
        return udp_uuid
    logger.error(f"get_transport_uuid_failed status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def get_global_template_uuid(admin_token: str, tenant_uuid: str):
    logger.info(f"get_global_template_uuid_start tenant_uuid={tenant_uuid}")
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/templates?recurse=false"
    start = time.perf_counter()
    try:
        resp = requests.get(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"get_global_template_uuid_request_error tenant_uuid={tenant_uuid} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 200:
        payload = resp.json()
        template_obj = next(
            (item for item in payload.get("items", []) if item.get("label") == "global"),
            None,
        )
        if not template_obj:
            logger.error(f"get_global_template_uuid_not_found tenant_uuid={tenant_uuid} duration_ms={duration_ms}")
            return False
        global_uuid = template_obj.get("uuid")
        logger.info(f"get_global_template_uuid_success tenant_uuid={tenant_uuid} uuid={global_uuid} duration_ms={duration_ms}")
        return global_uuid
    logger.error(f"get_global_template_uuid_failed tenant_uuid={tenant_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def create_user_voicemail(
    wazo_user_id: str,
    tenant_uuid: str,
    admin_token: str,
    context_name: str,
    email: str,
    extension_number: str,
    pin: str,
    name: str,
    max_messages: int = 10,
    language: str = "en_US",
    timezone: str = "na-newfoundland",
) -> Tuple[str, str , bool]:
    """
    Create a voicemail for a Wazo user.
    """

    url = f"{WAZO_API_URL}/api/confd/1.1/users/{wazo_user_id}/voicemails"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
        "Wazo-Tenant": tenant_uuid,
    }

    payload = {
        "ask_password": True,
        "attach_audio": True,
        "context": context_name,
        "delete_messages": False,
        "email": email,
        "enabled": True,
        "language": language,
        "max_messages": max_messages,
        "number": str(extension_number),
        "password": str(pin),
        "timezone": timezone,
        "name": name,
    }

    start = time.perf_counter()
    logger.info(f"create_voicemail_start tenant_uuid={tenant_uuid} wazo_user_id={wazo_user_id} extension={extension_number} context={context_name} url={url}")
    try:
        resp = requests.post(url, headers=headers, json=payload, verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"create_voicemail_request_error tenant_uuid={tenant_uuid} wazo_user_id={wazo_user_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 201:
        try:
            data = resp.json()
            enabled_raw = data.get("enabled")
            enabled_flag = enabled_raw if isinstance(enabled_raw, bool) else str(enabled_raw).lower() == "true"
            logger.info(f"create_voicemail_success tenant_uuid={tenant_uuid} wazo_user_id={wazo_user_id} voicemail_id={data.get('id')} enabled={enabled_flag} duration_ms={duration_ms}")
            return (
                data.get("id"),
                data.get("password"),
                enabled_flag,
            )
        except (ValueError, KeyError) as e:
            logger.error(f"create_voicemail_parse_error tenant_uuid={tenant_uuid} wazo_user_id={wazo_user_id} error={e} duration_ms={duration_ms}")
            return None, None, None

    logger.error(f"create_voicemail_failed tenant_uuid={tenant_uuid} wazo_user_id={wazo_user_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False



# ============ ROLLBACK / DELETE HELPERS ============

def deassociate_user_with_voicemail(admin_token: str, tenant_uuid: str, wazo_user_id: str) -> bool:
    """
    Remove voicemail associations from a user.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/users/{wazo_user_id}/voicemails"
    start = time.perf_counter()
    logger.info(f"deassociate_user_with_voicemail_start tenant_uuid={tenant_uuid} user_uuid={wazo_user_id} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"deassociate_user_with_voicemail_request_error tenant_uuid={tenant_uuid} user_uuid={wazo_user_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 204):
        logger.info(f"deassociate_user_with_voicemail_success tenant_uuid={tenant_uuid} user_uuid={wazo_user_id} duration_ms={duration_ms}")
        return True
    logger.error(f"deassociate_user_with_voicemail_failed tenant_uuid={tenant_uuid} user_uuid={wazo_user_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False

def delete_voicemail(admin_token: str, tenant_uuid: str, voicemail_id: str | int) -> bool:
    """
    Delete a voicemail by ID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/voicemails/{voicemail_id}"
    start = time.perf_counter()
    logger.info(f"delete_voicemail_start tenant_uuid={tenant_uuid} voicemail_id={voicemail_id} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"delete_voicemail_request_error tenant_uuid={tenant_uuid} voicemail_id={voicemail_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 204):
        logger.info(f"delete_voicemail_success tenant_uuid={tenant_uuid} voicemail_id={voicemail_id} duration_ms={duration_ms}")
        return True
    logger.error(f"delete_voicemail_failed tenant_uuid={tenant_uuid} voicemail_id={voicemail_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False

def unassign_line_with_sip_endpoint(admin_token: str, tenant_uuid: str, line_id: int, sip_uuid: str) -> bool:
    """
    Detach a SIP endpoint from a line.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/endpoints/sip/{sip_uuid}"
    start = time.perf_counter()
    logger.info(f"rollback_unassign_sip_start tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_unassign_sip_request_error tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"rollback_unassign_sip_success tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_unassign_sip_failed tenant_uuid={tenant_uuid} line_id={line_id} sip_uuid={sip_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def unassign_line_with_extension(admin_token: str, tenant_uuid: str, line_id: int, extension_id: int) -> bool:
    """
    Detach a line from an extension.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/extensions/{extension_id}"
    start = time.perf_counter()
    logger.info(f"rollback_unassign_line_from_extension_start tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_unassign_line_from_extension_request_error tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"rollback_unassign_line_from_extension_success tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_unassign_line_from_extension_failed tenant_uuid={tenant_uuid} line_id={line_id} extension_id={extension_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def unassign_user_with_line(admin_token: str, tenant_uuid: str, user_uuid: str, line_id: int) -> bool:
    """
    Detach a line from a user.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_uuid}/lines/{line_id}"
    start = time.perf_counter()
    logger.info(f"rollback_unassign_line_from_user_start tenant_uuid={tenant_uuid} line_id={line_id} user_uuid={user_uuid} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_unassign_line_from_user_request_error tenant_uuid={tenant_uuid} line_id={line_id} user_uuid={user_uuid} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code == 204:
        logger.info(f"rollback_unassign_line_from_user_success tenant_uuid={tenant_uuid} line_id={line_id} user_uuid={user_uuid} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_unassign_line_from_user_failed tenant_uuid={tenant_uuid} line_id={line_id} user_uuid={user_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def delete_sip_endpoint(admin_token: str, tenant_uuid: str, sip_uuid: str) -> bool:
    """
    Delete a SIP endpoint by UUID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/{sip_uuid}"
    start = time.perf_counter()
    logger.info(f"rollback_delete_sip_endpoint_start tenant_uuid={tenant_uuid} sip_uuid={sip_uuid} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_delete_sip_endpoint_request_error tenant_uuid={tenant_uuid} sip_uuid={sip_uuid} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 204):
        logger.info(f"rollback_delete_sip_endpoint_success tenant_uuid={tenant_uuid} sip_uuid={sip_uuid} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_delete_sip_endpoint_failed tenant_uuid={tenant_uuid} sip_uuid={sip_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def delete_line(admin_token: str, tenant_uuid: str, line_id: int) -> bool:
    """
    Delete a line by ID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}"
    start = time.perf_counter()
    logger.info(f"rollback_delete_line_start tenant_uuid={tenant_uuid} line_id={line_id} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_delete_line_request_error tenant_uuid={tenant_uuid} line_id={line_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 204):
        logger.info(f"rollback_delete_line_success tenant_uuid={tenant_uuid} line_id={line_id} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_delete_line_failed tenant_uuid={tenant_uuid} line_id={line_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def delete_extension(admin_token: str, tenant_uuid: str, extension_id: int) -> bool:
    """
    Delete an extension by ID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/extensions/{extension_id}"
    start = time.perf_counter()
    logger.info(f"rollback_delete_extension_start tenant_uuid={tenant_uuid} extension_id={extension_id} url={url}")
    try:
        resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"rollback_delete_extension_request_error tenant_uuid={tenant_uuid} extension_id={extension_id} error={exc} duration_ms={duration_ms}")
        return False
    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code in (200, 204):
        logger.info(f"rollback_delete_extension_success tenant_uuid={tenant_uuid} extension_id={extension_id} duration_ms={duration_ms}")
        return True
    logger.error(f"rollback_delete_extension_failed tenant_uuid={tenant_uuid} extension_id={extension_id} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False