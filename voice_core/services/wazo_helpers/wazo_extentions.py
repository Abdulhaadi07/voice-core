from config.settings.base import WAZO_API_URL
import requests
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


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
    logger.info(f"Creating Wazo line in context '{context_name}' for tenant {tenant_uuid}")
    resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    if resp.status_code in (200, 201):
        payload = resp.json()
        line_id = int(payload.get("id"))
        provisioning_extension = payload.get("provisioning_extension", "")
        logger.info(f"Created Wazo line id={line_id} provisioning_extension={provisioning_extension}")
        return line_id, provisioning_extension
    logger.error(f"Failed to create line: {resp.status_code} {resp.text}")
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
    logger.info(f"Creating Wazo extension exten={exten} in context '{context_name}' for tenant {tenant_uuid}")
    resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    if resp.status_code in (200, 201):
        payload = resp.json()
        extension_id = int(payload.get("id"))
        logger.info(f"Created Wazo extension id={extension_id} for exten={exten}")
        return extension_id
    logger.error(f"Failed to create extension: {resp.status_code} {resp.text}")
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
    global_template_uuid = get_global_template_uuid(admin_token,tenant_uuid)
    logger.info(f"transport_udp_uuid: {transport_udp_uuid}, global_template_uuid:{global_template_uuid}")
    data = {
        "auth_section_options": [["username", username], ["password", password]],
        "endpoint_section_options": [["rewrite_contact", "yes"], ["force_rport", "yes"],["rtp_symmetric", "yes"]],
        "label": label,
        "name": username,
        "templates": [{"uuid": global_template_uuid}],
        "transport": {"uuid": transport_udp_uuid}
    }
    logger.info(f"Creating Wazo SIP endpoint label='{label}' for tenant {tenant_uuid}")
    resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=data, verify=False)
    if resp.status_code in (200, 201):
        payload = resp.json()
        endpoint_uuid = payload["uuid"]
        endpoint_label =  payload["label"]
        endpoint_name =  payload["name"]
        logger.info(f"Created SIP endpoint uuid={endpoint_uuid}")
        return endpoint_uuid, endpoint_label, endpoint_name
    logger.error(f"Failed to create SIP endpoint: {resp.status_code} {resp.text}")
    resp.raise_for_status()


def assign_line_with_sip_endpoint(admin_token: str, tenant_uuid: str, line_id: int, sip_uuid: str) -> bool:
    """
    Attach a SIP endpoint to a line. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/endpoints/sip/{sip_uuid}"
    logger.info(f"Assigning SIP endpoint {sip_uuid} to line {line_id}")
    resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to assign SIP to line: {resp.status_code} {resp.text}")
    return False


def assign_line_with_extension(admin_token: str, tenant_uuid: str, line_id: int, extension_id: int) -> bool:
    """
    Attach a line to an extension. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/extensions/{extension_id}"
    logger.info(f"Assigning line {line_id} to extension {extension_id}")
    resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to assign line to extension: {resp.status_code} {resp.text}")
    return False


def assign_user_with_line(admin_token: str, tenant_uuid: str, user_uuid: str, line_id: int) -> bool:
    """
    Attach a line to a user. Returns True on success.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_uuid}/lines/{line_id}"
    logger.info(f"Assigning user {user_uuid} with line {line_id}")
    resp = requests.put(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to assign user with line: {resp.status_code} {resp.text}")
    return False

def get_transport_uuid(admin_token: str):
    url = f"{WAZO_API_URL}/api/confd/1.1/sip/transports"
    logger.info(f"Getting Transport upd uuid ")
    resp = requests.get(url, headers=_headers(admin_token), verify=False)
    if resp.status_code == 200:
        payload = resp.json()
        transport_udp_obj = next(
            (item for item in payload.get("items", []) if item.get("name") == "transport-udp"),
            None
        )
        udp_uuid = transport_udp_obj.get("uuid")
        logger.info(f"Transport upd uuid: {udp_uuid}")
        if not transport_udp_obj:
            raise ValueError("Transport 'transport-udp' not found in payload")

        return udp_uuid
    logger.error(f"Failed to udp transport: {resp.status_code} {resp.text}")
    return False


def get_global_template_uuid(admin_token: str, tenant_uuid: str):
    logger.info(f"Getting Global template uuid ")
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/templates?recurse=false"
    resp = requests.get(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 200:
        payload = resp.json()
        transport_udp_obj = next(
            (item for item in payload.get("items", []) if item.get("label") == "global"),
            None
        )
        global_uuid = transport_udp_obj.get("uuid")
        logger.info(f"Global template uuid: {global_uuid}")
        if not transport_udp_obj:
            raise ValueError("Template 'global' not found in payload")

        return global_uuid
    logger.error(f"Failed to get global template: {resp.status_code} {resp.text}")
    return False


def create_voicemail(
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
) -> tuple[str | None, str | None, bool | None]:
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

    resp = requests.post(url, headers=headers, json=payload, verify=False)
    if resp.status_code == 201:
        try:
            data = resp.json()
            enabled_raw = data.get("enabled")
            if isinstance(enabled_raw, bool):
                enabled_flag = enabled_raw
            else:
                enabled_flag = str(enabled_raw).lower() == "true"
            
            return (
                data.get("id"),
                data.get("password"),
                enabled_flag
            )
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse response JSON: {e}")
            return None, None, None

    logger.error(f"Failed to create voicemail for user {wazo_user_id}: {resp.status_code} {resp.text}")
    return False

# curl -X 'POST' \
#   'https://35.169.30.120/api/confd/1.1/users/9483eb79-497b-4867-b867-26c996d39a9b/voicemails' \
#   -H 'accept: application/json' \
#   -H 'Wazo-Tenant: ff2d1406-88bf-4a8d-bd9d-7f7bb03a79c8' \
#   -H 'Content-Type: application/json' \
#   -H 'X-Auth-Token: ddb33c3d-6c1e-4e19-ac19-6bd2074b40c0' \
#   -d '{
#   "ask_password": true,
#   "attach_audio": true,
#   "context": "ctx-aug203com-internal-6f1589b9-760b-4965-910a-afc4f0de246d",
#   "delete_messages": false,
#   "email": "withAuthU2T80@aug203.com",
#   "enabled": true,
#   "language": "en_US",
#   "max_messages": 10,
#   "number": "142",
  
#   "password": "1234",
#   "timezone": "na-newfoundland",
#   "name": "test2"
# }'

# ============ ROLLBACK / DELETE HELPERS ============

def unassign_line_with_sip_endpoint(admin_token: str, tenant_uuid: str, line_id: int, sip_uuid: str) -> bool:
    """
    Detach a SIP endpoint from a line.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/endpoints/sip/{sip_uuid}"
    logger.info(f"Unassigning SIP endpoint {sip_uuid} from line {line_id}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to unassign SIP from line: {resp.status_code} {resp.text}")
    return False


def unassign_line_with_extension(admin_token: str, tenant_uuid: str, line_id: int, extension_id: int) -> bool:
    """
    Detach a line from an extension.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}/extensions/{extension_id}"
    logger.info(f"Unassigning line {line_id} from extension {extension_id}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to unassign line from extension: {resp.status_code} {resp.text}")
    return False


def unassign_user_with_line(admin_token: str, tenant_uuid: str, user_uuid: str, line_id: int) -> bool:
    """
    Detach a line from a user.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/users/{user_uuid}/lines/{line_id}"
    logger.info(f"Unassigning line {line_id} from user {user_uuid}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code == 204:
        return True
    logger.error(f"Failed to unassign line from user: {resp.status_code} {resp.text}")
    return False


def delete_sip_endpoint(admin_token: str, tenant_uuid: str, sip_uuid: str) -> bool:
    """
    Delete a SIP endpoint by UUID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/{sip_uuid}"
    logger.info(f"Deleting SIP endpoint {sip_uuid}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code in (200, 204):
        return True
    logger.error(f"Failed to delete SIP endpoint: {resp.status_code} {resp.text}")
    return False


def delete_line(admin_token: str, tenant_uuid: str, line_id: int) -> bool:
    """
    Delete a line by ID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/lines/{line_id}"
    logger.info(f"Deleting line {line_id}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code in (200, 204):
        return True
    logger.error(f"Failed to delete line: {resp.status_code} {resp.text}")
    return False


def delete_extension(admin_token: str, tenant_uuid: str, extension_id: int) -> bool:
    """
    Delete an extension by ID.
    """
    url = f"{WAZO_API_URL}/api/confd/1.1/extensions/{extension_id}"
    logger.info(f"Deleting extension {extension_id}")
    resp = requests.delete(url, headers=_headers(admin_token, tenant_uuid), verify=False)
    if resp.status_code in (200, 204):
        return True
    logger.error(f"Failed to delete extension: {resp.status_code} {resp.text}")
    return False