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

def get_sip_global_template(admin_token: str, tenant_uuid: str):

    logger.info("get_sip_global_template start")
    tenant_global_uuid = get_tenant_global_template_uuid(admin_token, tenant_uuid)

    if tenant_global_uuid:
        logger.info("get_sip_global_template gets from tenant_tempalte without copy from master")
        return tenant_global_uuid
    
    # Tenant doesn't have a global template — fetch master
    master_template = get_master_global_template(admin_token)

    if not master_template:
        logger.error("Master global template not found, cannot create tenant template")
        return None

    new_uuid = create_tenant_global_template(admin_token, tenant_uuid, master_template)
    if not new_uuid:
        logger.error(f"Failed to create tenant global template for tenant {tenant_uuid}")
        return None

    return new_uuid


def get_tenant_global_template_uuid(admin_token: str, tenant_uuid: str):
    logger.info(f"get_global_template_uuid_start at wazo sip get or create for tenant_uuid={tenant_uuid}")
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
            return None
        global_uuid = template_obj.get("uuid")
        logger.info(f"get_global_template_uuid_success tenant_uuid={tenant_uuid} uuid={global_uuid} duration_ms={duration_ms}")
        return global_uuid
    logger.error(f"get_global_template_uuid_failed tenant_uuid={tenant_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
    return False


def get_master_global_template(admin_token: str) -> dict | None:
    """
    Fetch the master global SIP template (label = global).
    Returns the full template object dict or None if not found.
    """
    logger.info("get_master_global_template start")
    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/templates?recurse=false"
    start = time.perf_counter()
    try:
        resp = requests.get(url, headers=_headers(admin_token), verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"get_master_global_template_request_error error={exc} duration_ms={duration_ms}")
        return None

    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code != 200:
        logger.error(f"get_master_global_template_failed status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
        return None

    payload = resp.json()
    template_obj = next((item for item in payload.get("items", []) if item.get("label") == "global"), None)
    if not template_obj:
        logger.error(f"get_master_global_template_not_found duration_ms={duration_ms}")
        return None

    logger.info(f"get_master_global_template_success uuid={template_obj.get('uuid')} duration_ms={duration_ms}")
    return template_obj


def create_tenant_global_template(admin_token: str, tenant_uuid: str, master_global_template: dict) -> str | None:
    """
    Create a tenant's global template by cloning from master.
    Returns new tenant template UUID if successful, else None.
    """
    logger.info("create_tenant_global_template start")

    # Remove fields that shouldn't be posted (uuid, tenant_uuid, name.)
    payload = {k: v for k, v in master_global_template.items() if k not in ["uuid", "tenant_uuid", "name"]}

    url = f"{WAZO_API_URL}/api/confd/1.1/endpoints/sip/templates"
    start = time.perf_counter()
    try:

        resp = requests.post(url, headers=_headers(admin_token, tenant_uuid), json=payload, verify=False)
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(f"create_tenant_global_template_request_error tenant_uuid={tenant_uuid} error={exc} duration_ms={duration_ms}")
        return None

    duration_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code not in (200, 201):
        logger.error(f"create_tenant_global_template_failed tenant_uuid={tenant_uuid} status={resp.status_code} body={_truncate(resp.text)} duration_ms={duration_ms}")
        return None

    new_template = resp.json()
    logger.info(f"create_tenant_global_template_success tenant_uuid={tenant_uuid} new_uuid={new_template.get('uuid')} duration_ms={duration_ms}")
    return new_template.get("uuid")


def delete_sip_template(template_uuid: str, admin_token: str) -> dict:
    """
    Deletes a SIP template by ID using the Confd API.

    Args:
        template_id (str): The UUID of the template to delete.
        auth_token (str): The authentication token for the API.
        base_url (str): Base URL of the Confd API.

    Returns:
        dict: JSON response from the API.
    """
    url = f"{WAZO_API_URL}/endpoints/sip/templates/{template_uuid}"
    headers = {
        "accept": "application/json",
        "X-Auth-Token": admin_token
    }

    response = requests.delete(url, headers=headers)

    # Raise an exception if the request failed
    response.raise_for_status()

    # Return JSON response
    return response.json() if response.content else {"message": "Deleted successfully"}