import requests
from typing import List
from config.settings.base import (
    EXTENSION_START_VALUE,
    WAZO_API_URL,
)
from voice_core.tenant.models import Tenant
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token

import logging
logger = logging.getLogger(__name__)


def create_context(tenant: Tenant):
    logger.info(f"Starting context creation for tenant: {tenant.name} (UUID: {tenant.wazo_tenant_uuid})")
    try:
        admin_token = get_wazo_admin_token()
        label = f"{tenant.name}-initial-context"
        extension_start_value = int(EXTENSION_START_VALUE)
        logger.info(f"extension_start_value: {extension_start_value}")
        user_ranges = [{"start": f"{str(extension_start_value)}", "end": f"{str(extension_start_value+tenant.max_users)}"}]
        context_type = "internal"
        
        logger.info(f"Creating Wazo context with label: {label}, type: {context_type}, user_ranges: {user_ranges}")
        context_data = create_wazo_context(admin_token, str(tenant.wazo_tenant_uuid), label, context_type, user_ranges)
        
        logger.info(f"Successfully created context for tenant {tenant.name}: context_data={context_data}")
        return context_data
        
    except Exception as e:
        logger.error(f"Failed to create context for tenant {tenant.name}: {str(e)}", exc_info=True)
        raise


def create_wazo_context(admin_token: str, 
                    tenant_uuid: str, 
                    label: str, 
                    context_type: str = "internal", 
                    user_ranges: List[dict] = None) -> dict:
    """
    Create a context in Wazo for a specific tenant.
    """
    logger.info(f"Making Wazo API call to create context: {label} for tenant: {tenant_uuid}")
    logger.debug(f"Context details - type: {context_type}, user_ranges: {user_ranges}")

    url = f"{WAZO_API_URL}/api/confd/1.1/contexts"
    
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Auth-Token': admin_token,
        'Wazo-Tenant': tenant_uuid,
    }
    
    data = {
        "label": label,
        "type": context_type,
        "user_ranges": user_ranges
    }
    
    try:
        logger.debug(f"Sending POST request to: {url}")
        response = requests.post(url, headers=headers, json=data, verify=False)
        
        if response.status_code == 201:
            response_data = response.json()
            context_data = {
                "uuid": response_data['uuid'],
                "name": response_data['name'],
                "label": response_data['label'],
                "user_ranges": response_data['user_ranges']
            }
            
            logger.info(f"Wazo context created successfully - context_data: {context_data}")
            return context_data
            
        else:
            logger.error(f"Wazo API returned error status: {response.status_code}, response: {response.text}")
            response.raise_for_status()
            
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed for context creation: {str(e)}", exc_info=True)
        raise
    except KeyError as e:
        logger.error(f"Unexpected response format from Wazo API: missing key {str(e)}, response: {response.text}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during context creation: {str(e)}", exc_info=True)
        raise